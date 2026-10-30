"""World-model planning with high-fidelity candidate verification."""
from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Callable

import numpy as np

from .plant import MODE_DERATE, MODE_FULL, MODE_MAINTENANCE, MODE_OFF, ProductionPlant
from .world_model import EnsembleWorldModel


@dataclass
class Plan:
    modes: np.ndarray
    predicted_profit: float
    predicted_uncertainty: float
    predicted_risk: float
    verified_profit: float | None = None
    verified_failures: int = 0
    verified_unmet: float = 0.0
    verified_capacity_violations: int = 0
    verified_risk: float = 0.0
    verified_robust_score: float | None = None
    verified_failure_probability: float = 0.0
    verified_failures_p90: float = 0.0
    verified_cvar10: float = 0.0


def _mode_cost(mode: int) -> float:
    return {MODE_OFF: 0.0, MODE_DERATE: 0.0, MODE_FULL: 0.0, MODE_MAINTENANCE: 420.0}.get(int(mode), 0.0)


def _objective_terms(plant: ProductionPlant, state: np.ndarray, modes: np.ndarray) -> tuple[float, float, float]:
    """Approximate risk and capacity terms from a predicted state."""
    n = plant.n_machines
    health = np.clip(state[:n], 0.0, 1.0)
    risk = float(np.mean(np.maximum(0.0, 0.62 - health) ** 2))
    loads = np.where(modes == MODE_FULL, 1.0, np.where(modes == MODE_DERATE, 0.58, 0.0))
    available = np.array([spec.capacity for spec in plant.specs]) * loads * (0.78 + 0.22 * health)
    capacity_violation = max(0.0, plant.demand(int(round(state[-4] * 0.0))) - available.sum())
    return risk, capacity_violation, float(np.sum(loads))


def safety_shield(plant: ProductionPlant, modes: np.ndarray) -> np.ndarray:
    """Apply a deterministic safety filter to a requested joint action.

    This is deliberately independent of the learned world model. Low-health or
    overheated machines are derated or maintained before they can reach a
    failure-prone state. The same shield is applied during verification and
    execution so a plan cannot silently diverge between the two paths.
    """
    assert plant.state is not None
    requested = np.asarray(modes, dtype=int).copy()
    s = plant.state
    for i in range(plant.n_machines):
        if s.down_remaining[i] > 0.0 or s.maintenance_remaining[i] > 0.0:
            continue
        health = float(s.health[i])
        hot = float(s.temperature[i]) > plant.ambient_temp + 25.0
        if health < 0.42:
            requested[i] = MODE_MAINTENANCE
        elif (health < 0.68 or hot) and requested[i] == MODE_FULL:
            requested[i] = MODE_DERATE
    return requested


def simulate_world_plan(
    model: EnsembleWorldModel,
    plant: ProductionPlant,
    initial_state: np.ndarray,
    plan_modes: np.ndarray,
    risk_weight: float = 1800.0,
    uncertainty_weight: float = 60.0,
) -> tuple[float, float, float, float]:
    state = np.asarray(initial_state, dtype=float).copy()
    total_profit = 0.0
    total_risk = 0.0
    total_uncertainty = 0.0
    for t, mode in enumerate(plan_modes):
        next_state, profit, unc = model.predict_step(state, np.asarray(mode, dtype=int))
        # Refresh forecast-only global features from the known scenario.
        hour = int(plant.state.hour + t) if plant.state is not None else t
        phase = 2.0 * np.pi * (hour % 24) / 24.0
        next_state[-5] = np.sin(phase)
        next_state[-4] = np.cos(phase)
        next_state[-3] = plant.demand(hour) / 100.0
        next_state[-2] = plant.energy_price(hour) / 0.2
        total_profit += profit
        total_risk += float(np.mean(np.maximum(0.0, 0.62 - np.clip(next_state[: plant.n_machines], 0.0, 1.0)) ** 2))
        total_uncertainty += unc
        state = next_state
    score = total_profit - risk_weight * total_risk - uncertainty_weight * total_uncertainty
    return float(score), float(total_profit), float(total_risk), float(total_uncertainty)


class CEMPlanner:
    """Cross-entropy-method planner over joint machine modes."""

    def __init__(
        self,
        horizon: int = 24,
        population: int = 64,
        elite: int = 8,
        iterations: int = 4,
        seed: int = 20261008,
        risk_weight: float = 1800.0,
        uncertainty_weight: float = 60.0,
        robust_verify: bool = True,
    ) -> None:
        self.horizon = int(horizon)
        self.population = int(population)
        self.elite = int(elite)
        self.iterations = int(iterations)
        self.seed = int(seed)
        self.risk_weight = float(risk_weight)
        self.uncertainty_weight = float(uncertainty_weight)
        self.robust_verify = bool(robust_verify)

    def plan(
        self,
        model: EnsembleWorldModel,
        plant: ProductionPlant,
        verify_candidates: int = 0,
    ) -> Plan:
        assert plant.state is not None
        rng = np.random.default_rng(self.seed + plant.state.hour * 7)
        n = plant.n_machines
        probs = np.tile(np.array([0.08, 0.18, 0.60, 0.14]), (self.horizon, n, 1))
        best_modes = np.zeros((self.horizon, n), dtype=int)
        best_score = -1e18
        best_terms = (0.0, 0.0, 0.0)
        state = plant.observation()
        for _ in range(self.iterations):
            samples = np.zeros((self.population, self.horizon, n), dtype=int)
            for t in range(self.horizon):
                for i in range(n):
                    samples[:, t, i] = rng.choice(4, size=self.population, p=probs[t, i])
            scored: list[tuple[float, int, tuple[float, float, float]]] = []
            for k in range(self.population):
                score, profit, risk, uncertainty = simulate_world_plan(
                    model, plant, state, samples[k], self.risk_weight, self.uncertainty_weight
                )
                scored.append((score, k, (profit, risk, uncertainty)))
            scored.sort(key=lambda x: x[0], reverse=True)
            elites = scored[: self.elite]
            if elites[0][0] > best_score:
                best_score, best_terms = elites[0][0], elites[0][2]
                best_modes = samples[elites[0][1]].copy()
            for t in range(self.horizon):
                for i in range(n):
                    counts = np.bincount(samples[[e[1] for e in elites], t, i], minlength=4).astype(float)
                    probs[t, i] = (counts + 0.25) / (counts.sum() + 1.0)
        plan = Plan(
            modes=best_modes,
            predicted_profit=best_terms[0],
            predicted_uncertainty=best_terms[2],
            predicted_risk=best_terms[1],
        )
        if verify_candidates > 0:
            alternatives = [best_modes]
            # Use the top CEM candidates as independent verification candidates,
            # rather than semantically arbitrary one-column perturbations.
            for _, candidate_idx, _ in scored[: max(1, verify_candidates)]:
                candidate = samples[candidate_idx].copy()
                if not any(np.array_equal(candidate, existing) for existing in alternatives):
                    alternatives.append(candidate)
                if len(alternatives) >= max(1, verify_candidates):
                    break
            verified: list[tuple[float, np.ndarray, tuple[float, int, float, int, float, float, float, float]]] = []
            for candidate in alternatives:
                result = verify_plan(plant, candidate)
                key = float(result["robust_score"]) if self.robust_verify else float(result["score"])
                verified.append((
                    key,
                    candidate,
                    (
                        float(result["profit"]),
                        int(result["failures"]),
                        float(result["unmet"]),
                        int(result["capacity_violations"]),
                        float(result["risk"]),
                        float(result["robust_score"]),
                        float(result["failure_probability"]),
                        float(result["failures_p90"]),
                    ),
                ))
            verified.sort(key=lambda x: x[0], reverse=True)
            score, chosen, vals = verified[0]
            plan.modes = chosen
            plan.verified_profit = vals[0]
            plan.verified_failures = vals[1]
            plan.verified_unmet = vals[2]
            plan.verified_capacity_violations = vals[3]
            plan.verified_risk = vals[4]
            plan.verified_robust_score = vals[5]
            plan.verified_failure_probability = vals[6]
            plan.verified_failures_p90 = vals[7]
            plan.verified_cvar10 = float(verify_plan(plant, chosen)["profit_cvar10"])
        return plan


def verify_plan(
    plant: ProductionPlant,
    modes: np.ndarray,
    scenario_seeds: tuple[int, ...] | None = None,
) -> dict[str, float | int]:
    """Roll out a plan across independent high-fidelity validation scenarios.

    Reports both expected values and tail-risk statistics. The mean is used for
    planner ranking; the probability/quantile fields are used for deployment
    review so a single lucky or unlucky trajectory is not hidden.
    """
    if scenario_seeds is None:
        scenario_seeds = tuple(7100 + i for i in range(8))
    profits: list[float] = []
    failures_list: list[int] = []
    unmet_list: list[float] = []
    violations_list: list[int] = []
    final_health: list[float] = []
    shield_adjustments = 0
    for scenario in scenario_seeds:
        clone = plant.clone_for_validation(int(scenario) + plant.state.hour * 17 if plant.state else int(scenario))
        total_profit = 0.0
        failures = 0
        unmet = 0.0
        violations = 0
        for mode in modes:
            requested = np.asarray(mode, dtype=int)
            effective = safety_shield(clone, requested)
            shield_adjustments += int(np.sum(effective != requested))
            _, profit, _, info = clone.step(effective)
            total_profit += profit
            failures += info.failures
            unmet += info.unmet
            if info.capacity_margin < -0.5:
                violations += 1
        profits.append(float(total_profit))
        failures_list.append(int(failures))
        unmet_list.append(float(unmet))
        violations_list.append(int(violations))
        if clone.state is not None:
            final_health.append(float(np.mean(clone.state.health)))
    profit_arr = np.asarray(profits, dtype=float)
    failure_arr = np.asarray(failures_list, dtype=float)
    unmet_arr = np.asarray(unmet_list, dtype=float)
    violation_arr = np.asarray(violations_list, dtype=float)
    mean_profit = float(profit_arr.mean())
    mean_failures = float(failure_arr.mean())
    mean_unmet = float(unmet_arr.mean())
    mean_violations = float(violation_arr.mean())
    n_scenarios = max(1, len(profits))
    score = mean_profit - 3000.0 * mean_failures - 80.0 * mean_unmet - 900.0 * mean_violations
    health_risk = float(np.mean(np.maximum(0.0, 0.62 - np.asarray(final_health)) ** 2)) if final_health else 0.0
    worst_count = max(1, int(np.ceil(0.1 * n_scenarios)))
    cvar_profit = float(np.sort(profit_arr)[:worst_count].mean())
    return {
        "score": float(score),
        "profit": mean_profit,
        "profit_std": float(profit_arr.std()),
        "profit_min": float(profit_arr.min()),
        "profit_p05": float(np.percentile(profit_arr, 5)),
        "profit_p50": float(np.percentile(profit_arr, 50)),
        "profit_p95": float(np.percentile(profit_arr, 95)),
        "profit_cvar10": cvar_profit,
        "failures": int(round(mean_failures)),
        "failure_probability": float(np.mean(failure_arr > 0)),
        "failures_p50": float(np.percentile(failure_arr, 50)),
        "failures_p90": float(np.percentile(failure_arr, 90)),
        "failures_p95": float(np.percentile(failure_arr, 95)),
        "failures_max": int(failure_arr.max()),
        "unmet": mean_unmet,
        "unmet_p90": float(np.percentile(unmet_arr, 90)),
        "unmet_p95": float(np.percentile(unmet_arr, 95)),
        "unmet_max": float(unmet_arr.max()),
        "capacity_violations": int(round(mean_violations)),
        "capacity_violations_max": int(violation_arr.max()),
        "risk": health_risk,
        "shield_adjustments": int(shield_adjustments),
        "robust_score": float(
            cvar_profit
            - 3000.0 * float(np.percentile(failure_arr, 90))
            - 80.0 * float(np.percentile(unmet_arr, 90))
            - 900.0 * float(violation_arr.max())
        ),
    }
