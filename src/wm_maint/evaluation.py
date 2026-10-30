"""Evaluation harness: baselines, world-model policies and verification metrics."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Callable

import numpy as np

from .data import collect_transitions
from .plant import MODE_FULL, MODE_MAINTENANCE, ProductionPlant, encode_modes
from .planner import CEMPlanner, Plan, safety_shield, verify_plan
from .world_model import EnsembleWorldModel


@dataclass
class EpisodeMetrics:
    seed: int
    hours: int
    profit: float
    production: float
    fulfilled: float
    unmet: float
    energy_cost: float
    maintenance_cost: float
    failure_cost: float
    downtime_penalty: float
    unmet_penalty: float
    failures: int
    maintenances: int
    downtime_hours: float
    final_mean_health: float
    min_health: float
    elapsed_s: float
    capacity_violations: int = 0


@dataclass
class PlanAudit:
    seed: int
    hour: int
    predicted_profit: float
    verified_profit: float
    prediction_error: float
    verified_failures: int
    verified_unmet: float
    capacity_violations: int
    verified_robust_score: float = 0.0
    verified_failure_probability: float = 0.0
    verified_failures_p90: float = 0.0
    verified_cvar10: float = 0.0


@dataclass
class EvaluationResult:
    name: str
    episodes: list[EpisodeMetrics]
    plan_audits: list[PlanAudit] = field(default_factory=list)
    oracle_gap_pct: float | None = None

    def summary(self) -> dict[str, float]:
        if not self.episodes:
            return {}
        arr = lambda key: np.array([getattr(e, key) for e in self.episodes], dtype=float)
        return {
            "episodes": float(len(self.episodes)),
            "profit_mean": float(arr("profit").mean()),
            "profit_std": float(arr("profit").std()),
            "production_mean": float(arr("production").mean()),
            "unmet_mean": float(arr("unmet").mean()),
            "failures_mean": float(arr("failures").mean()),
            "maintenances_mean": float(arr("maintenances").mean()),
            "downtime_hours_mean": float(arr("downtime_hours").mean()),
            "final_health_mean": float(arr("final_mean_health").mean()),
            "min_health_mean": float(arr("min_health").mean()),
            "elapsed_s_mean": float(arr("elapsed_s").mean()),
            "capacity_violations_mean": float(arr("capacity_violations").mean()),
            "plan_prediction_mae": float(np.mean([abs(a.prediction_error) for a in self.plan_audits])) if self.plan_audits else 0.0,
            "plan_prediction_wape_pct": (
                float(
                    np.sum([abs(a.prediction_error) for a in self.plan_audits])
                    / max(1.0, np.sum([abs(a.verified_profit) for a in self.plan_audits]))
                    * 100.0
                )
                if self.plan_audits
                else 0.0
            ),
            "verified_capacity_violations": float(np.sum([a.capacity_violations for a in self.plan_audits])) if self.plan_audits else 0.0,
            "verified_failure_probability_mean": float(np.mean([a.verified_failure_probability for a in self.plan_audits])) if self.plan_audits else 0.0,
            "verified_failures_p90_mean": float(np.mean([a.verified_failures_p90 for a in self.plan_audits])) if self.plan_audits else 0.0,
            "verified_cvar10_mean": float(np.mean([a.verified_cvar10 for a in self.plan_audits])) if self.plan_audits else 0.0,
        }


PolicyFn = Callable[[ProductionPlant, int], np.ndarray]


def run_episode(name: str, seed: int, hours: int, policy: PolicyFn, audit: list[PlanAudit] | None = None) -> EpisodeMetrics:
    plant = ProductionPlant(seed=seed, episode_hours=hours)
    start = time.perf_counter()
    total_profit = 0.0
    total_production = 0.0
    total_fulfilled = 0.0
    total_unmet = 0.0
    energy = maintenance_cost = failure_cost = downtime_penalty = unmet_penalty = 0.0
    failures = maintenances = 0
    downtime_hours = 0.0
    violations = 0
    min_health = 1.0
    for hour in range(hours):
        modes = np.asarray(policy(plant, hour), dtype=int)
        _, profit, done, info = plant.step(modes)
        total_profit += profit
        total_production += info.production
        total_fulfilled += info.fulfilled
        total_unmet += info.unmet
        energy += info.energy_cost
        maintenance_cost += info.maintenance_cost
        failure_cost += info.failure_cost
        downtime_penalty += info.downtime_penalty
        unmet_penalty += info.unmet_penalty
        failures += info.failures
        maintenances += info.maintenances
        downtime_hours += info.downtime_count
        if info.capacity_margin < -0.5:
            violations += 1
        min_health = min(min_health, float(np.min(plant.state.health)))
        if done:
            break
    assert plant.state is not None
    return EpisodeMetrics(
        seed=seed,
        hours=plant.state.hour,
        profit=float(total_profit),
        production=float(total_production),
        fulfilled=float(total_fulfilled),
        unmet=float(total_unmet),
        energy_cost=float(energy),
        maintenance_cost=float(maintenance_cost),
        failure_cost=float(failure_cost),
        downtime_penalty=float(downtime_penalty),
        unmet_penalty=float(unmet_penalty),
        failures=int(failures),
        maintenances=int(maintenances),
        downtime_hours=float(downtime_hours),
        final_mean_health=float(np.mean(plant.state.health)),
        min_health=float(min_health),
        elapsed_s=float(time.perf_counter() - start),
        capacity_violations=int(violations),
    )


def full_policy(plant: ProductionPlant, _: int) -> np.ndarray:
    return np.full(plant.n_machines, MODE_FULL, dtype=int)


def fixed_interval_policy(interval: int = 72) -> PolicyFn:
    def policy(plant: ProductionPlant, hour: int) -> np.ndarray:
        assert plant.state is not None
        modes = np.full(plant.n_machines, MODE_FULL, dtype=int)
        active = np.where(plant.state.maintenance_remaining > 0)[0]
        if active.size:
            modes[active] = MODE_MAINTENANCE
            return modes
        if hour > 0 and hour % interval == 0:
            eligible = [
                i for i in range(plant.n_machines)
                if plant.state.down_remaining[i] <= 0 and plant.state.maintenance_remaining[i] <= 0
            ]
            if eligible:
                idx = int(min(eligible, key=lambda i: plant.state.health[i]))
                modes[idx] = MODE_MAINTENANCE
        return modes
    return policy


def threshold_policy(plant: ProductionPlant, _: int) -> np.ndarray:
    assert plant.state is not None
    modes = np.full(plant.n_machines, MODE_FULL, dtype=int)
    active = np.where(plant.state.maintenance_remaining > 0)[0]
    if active.size:
        modes[active] = MODE_MAINTENANCE
        return modes
    risky = [
        i for i in range(plant.n_machines)
        if plant.state.health[i] < 0.46 or plant.state.temperature[i] > plant.ambient_temp + 24.0
    ]
    if risky:
        modes[int(min(risky, key=lambda i: plant.state.health[i]))] = MODE_MAINTENANCE
        return modes
    for i in range(plant.n_machines):
        if plant.state.health[i] < 0.66:
            modes[i] = 1
    return modes


class HighFidelityOraclePolicy:
    """Expensive CEM baseline that scores every candidate in the digital twin.

    This is an upper-reference planner, not a deployable online policy: it uses
    the independent validation scenarios for every candidate. The gap between
    this oracle and the world-model planner is the price of learned planning.
    """

    def __init__(
        self,
        plan_every: int = 6,
        horizon: int = 12,
        population: int = 12,
        elite: int = 4,
        iterations: int = 2,
        seed: int = 20261008,
    ) -> None:
        self.plan_every = int(plan_every)
        self.horizon = int(horizon)
        self.population = int(population)
        self.elite = int(elite)
        self.iterations = int(iterations)
        self.seed = int(seed)
        self.sequence: np.ndarray | None = None

    def __call__(self, plant: ProductionPlant, hour: int) -> np.ndarray:
        assert plant.state is not None
        if self.sequence is None or hour % self.plan_every == 0:
            rng = np.random.default_rng(self.seed + hour * 31)
            probs = np.tile(np.array([0.10, 0.18, 0.58, 0.14]), (self.horizon, plant.n_machines, 1))
            best = np.full((self.horizon, plant.n_machines), 2, dtype=int)
            best_score = -1e18
            for _ in range(self.iterations):
                samples = np.zeros((self.population, self.horizon, plant.n_machines), dtype=int)
                for t in range(self.horizon):
                    for i in range(plant.n_machines):
                        samples[:, t, i] = rng.choice(4, size=self.population, p=probs[t, i])
                scored = []
                for k, candidate in enumerate(samples):
                    result = verify_plan(plant, candidate)
                    scored.append((float(result["score"]), k))
                scored.sort(key=lambda item: item[0], reverse=True)
                if scored[0][0] > best_score:
                    best_score = scored[0][0]
                    best = samples[scored[0][1]].copy()
                elites = [item[1] for item in scored[: self.elite]]
                for t in range(self.horizon):
                    for i in range(plant.n_machines):
                        counts = np.bincount(samples[elites, t, i], minlength=4).astype(float)
                        probs[t, i] = (counts + 0.25) / (counts.sum() + 1.0)
            self.sequence = best
        return self.sequence[hour % self.plan_every]


class WorldModelPolicy:
    """CEM planning followed by independent high-fidelity candidate verification."""

    def __init__(
        self,
        model: EnsembleWorldModel,
        plan_every: int = 6,
        verify_candidates: int = 4,
        horizon: int = 24,
        population: int = 64,
        elite: int = 8,
        iterations: int = 4,
        seed: int = 20261008,
        robust_verify: bool = True,
        safety_shield_enabled: bool = True,
    ) -> None:
        self.model = model
        self.plan_every = int(plan_every)
        self.verify_candidates = int(verify_candidates)
        self.planner = CEMPlanner(
            horizon=horizon,
            population=population,
            elite=elite,
            iterations=iterations,
            seed=seed,
            robust_verify=robust_verify,
        )
        self.sequence: np.ndarray | None = None
        self.audits: list[PlanAudit] = []
        self.fallback_count = 0
        self.safety_shield_enabled = bool(safety_shield_enabled)

    def __call__(self, plant: ProductionPlant, hour: int) -> np.ndarray:
        assert plant.state is not None
        if self.sequence is None or hour % self.plan_every == 0:
            plan = self.planner.plan(self.model, plant, verify_candidates=self.verify_candidates)
            self.sequence = plan.modes.copy()
            if plan.verified_profit is not None:
                self.audits.append(
                    PlanAudit(
                        seed=plant.seed,
                        hour=hour,
                        predicted_profit=plan.predicted_profit,
                        verified_profit=plan.verified_profit,
                        prediction_error=plan.predicted_profit - plan.verified_profit,
                        verified_failures=plan.verified_failures,
                        verified_unmet=plan.verified_unmet,
                        capacity_violations=plan.verified_capacity_violations,
                        verified_robust_score=float(plan.verified_robust_score or 0.0),
                        verified_failure_probability=float(plan.verified_failure_probability),
                        verified_failures_p90=float(plan.verified_failures_p90),
                        verified_cvar10=float(plan.verified_cvar10),
                    )
                )
                if plan.verified_capacity_violations > 0 or plan.verified_profit <= 0.0:
                    self.fallback_count += 1
                    return threshold_policy(plant, hour)
        step = min(hour % self.plan_every, len(self.sequence) - 1)
        requested = self.sequence[step]
        if self.safety_shield_enabled:
            return safety_shield(plant, requested)
        return requested


def evaluate_policy(name: str, seeds: list[int], hours: int, policy_factory: Callable[[], PolicyFn]) -> EvaluationResult:
    episodes: list[EpisodeMetrics] = []
    audits: list[PlanAudit] = []
    for seed in seeds:
        policy = policy_factory()
        if isinstance(policy, WorldModelPolicy):
            episodes.append(run_episode(name, seed, hours, policy, policy.audits))
            audits.extend(policy.audits)
        else:
            episodes.append(run_episode(name, seed, hours, policy))
    return EvaluationResult(name=name, episodes=episodes, plan_audits=audits)


def evaluate_world_model(
    model: EnsembleWorldModel,
    test_seed: int = 909090,
    n_episodes: int = 8,
    episode_hours: int = 48,
) -> dict[str, float]:
    """One-step held-out prediction and uncertainty calibration metrics."""
    dataset = collect_transitions(n_episodes=n_episodes, episode_hours=episode_hours, seed=test_seed)
    pred = model.predict_raw(dataset.states, dataset.actions)
    n_machine = model.n_machines * 5
    target = np.concatenate(
        [
            dataset.next_states[:, :n_machine],
            np.clip(dataset.productions / 200.0, -2.0, 4.0).reshape(-1, 1),
            np.clip(dataset.profits / 1500.0, -4.0, 4.0).reshape(-1, 1),
        ],
        axis=1,
    )
    err = pred.mean - target
    machine_rmse = float(np.sqrt(np.mean(err[:, :n_machine] ** 2)))
    profit_mae = float(np.mean(np.abs(err[:, -1] * 1500.0)))
    health_idx = np.arange(0, n_machine, 5)
    health_rmse = float(np.sqrt(np.mean(err[:, health_idx] ** 2)))
    abs_std_z = np.abs(err) / (pred.std + 1e-3)
    coverage_1sigma = float(np.mean(abs_std_z <= 1.0))
    coverage_2sigma = float(np.mean(abs_std_z <= 2.0))
    return {
        "n_transitions": float(len(dataset.states)),
        "machine_state_rmse_normalized": machine_rmse,
        "health_rmse_normalized": health_rmse,
        "profit_mae": profit_mae,
        "coverage_1sigma": coverage_1sigma,
        "coverage_2sigma": coverage_2sigma,
    }

