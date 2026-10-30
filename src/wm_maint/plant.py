"""Independent high-fidelity reference simulator for a small production line.

The simulator is intentionally implemented separately from the learned world
model. It combines continuous degradation, thermal dynamics, stochastic
failure, maintenance downtime and production economics. It is the ground-truth
reference used to validate model rollouts and planned actions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
from typing import Iterable

import numpy as np

from .config import MachineSpec, default_machine_specs


MODE_OFF = 0
MODE_DERATE = 1
MODE_FULL = 2
MODE_MAINTENANCE = 3
MODE_NAMES = ("off", "derate", "full", "maintenance")
LOADS = np.array([0.0, 0.58, 1.0, 0.0], dtype=float)


@dataclass
class PlantSnapshot:
    hour: int
    health: np.ndarray
    temperature: np.ndarray
    vibration: np.ndarray
    age: np.ndarray
    down_remaining: np.ndarray
    maintenance_remaining: np.ndarray
    total_produced: float = 0.0
    cumulative_profit: float = 0.0
    cumulative_unmet: float = 0.0
    failure_count: int = 0
    maintenance_count: int = 0
    downtime_hours: float = 0.0


@dataclass
class PlantInfo:
    production: float
    fulfilled: float
    unmet: float
    energy_cost: float
    maintenance_cost: float
    failure_cost: float
    downtime_penalty: float
    unmet_penalty: float
    revenue: float
    profit: float
    failures: int
    maintenances: int
    downtime_count: float
    capacity_margin: float
    risk_score: float
    modes: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))


class ProductionPlant:
    """Stochastic reference plant with a discrete one-hour control interval."""

    ambient_temp = 26.0
    product_price = 22.0
    unmet_penalty_multiplier = 0.45
    downtime_hourly_penalty = 120.0

    def __init__(
        self,
        specs: tuple[MachineSpec, ...] | None = None,
        seed: int = 20261008,
        episode_hours: int = 168,
    ) -> None:
        self.specs = specs or default_machine_specs(3)
        self.n_machines = len(self.specs)
        self.seed = int(seed)
        self.episode_hours = int(episode_hours)
        self._rng = np.random.default_rng(self.seed)
        self.state: PlantSnapshot | None = None
        self.reset(seed=self.seed)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def reset(self, seed: int | None = None, initial_health: np.ndarray | None = None) -> PlantSnapshot:
        if seed is not None:
            self.seed = int(seed)
            self._rng = np.random.default_rng(self.seed)
        if initial_health is None:
            health = self._rng.uniform(0.72, 0.98, self.n_machines)
        else:
            health = np.asarray(initial_health, dtype=float).copy()
        self.state = PlantSnapshot(
            hour=0,
            health=np.clip(health, 0.05, 1.0),
            temperature=self._rng.normal(31.0, 1.4, self.n_machines),
            vibration=np.clip(0.12 + 0.20 * (1.0 - health) + self._rng.normal(0, 0.015, self.n_machines), 0.0, 1.0),
            age=np.zeros(self.n_machines, dtype=float),
            down_remaining=np.zeros(self.n_machines, dtype=float),
            maintenance_remaining=np.zeros(self.n_machines, dtype=float),
        )
        return self.snapshot()

    def clone_for_validation(self, seed: int) -> "ProductionPlant":
        """Copy current physical state but use an independent future scenario.

        A genuine digital-twin verification must not replay the production
        episode's private random draws. This method preserves the current state
        while replacing the future stochastic stream with a validation seed.
        """
        other = self.clone()
        other._rng = np.random.default_rng(int(seed))
        return other

    def clone(self) -> "ProductionPlant":
        other = object.__new__(ProductionPlant)
        other.specs = self.specs
        other.n_machines = self.n_machines
        other.seed = self.seed
        other.episode_hours = self.episode_hours
        other._rng = np.random.default_rng()
        other._rng.bit_generator.state = copy.deepcopy(self._rng.bit_generator.state)
        other.state = copy.deepcopy(self.state)
        return other

    def snapshot(self) -> PlantSnapshot:
        assert self.state is not None
        return copy.deepcopy(self.state)

    # ------------------------------------------------------------------
    # Forecasts and observations
    # ------------------------------------------------------------------
    def demand(self, hour: int) -> float:
        daily = 14.0 * math.sin(2.0 * math.pi * (hour % 24) / 24.0 - 0.7)
        weekly = 4.0 * math.sin(2.0 * math.pi * (hour % 168) / 168.0)
        return float(max(25.0, 66.0 + daily + weekly))

    def energy_price(self, hour: int) -> float:
        daily = 0.035 * math.sin(2.0 * math.pi * (hour % 24) / 24.0 + 0.5)
        peak = 0.018 if 8 <= (hour % 24) <= 19 else 0.0
        return float(max(0.055, 0.105 + daily + peak))

    def observation(self) -> np.ndarray:
        """Physical observation used by both world model and planner."""
        assert self.state is not None
        s = self.state
        machines = np.column_stack(
            [
                s.health,
                np.clip((s.temperature - 20.0) / 30.0, 0.0, 2.0),
                s.vibration,
                np.clip(s.down_remaining / 12.0, 0.0, 1.0),
                np.clip(s.maintenance_remaining / 3.0, 0.0, 1.0),
            ]
        ).reshape(-1)
        phase = 2.0 * math.pi * (s.hour % 24) / 24.0
        global_obs = np.array(
            [
                math.sin(phase),
                math.cos(phase),
                self.demand(s.hour) / 100.0,
                self.energy_price(s.hour) / 0.2,
                np.clip(s.total_produced / 10000.0, 0.0, 3.0),
            ],
            dtype=float,
        )
        return np.concatenate([machines, global_obs])

    @property
    def observation_dim(self) -> int:
        return self.n_machines * 5 + 5

    @staticmethod
    def action_dim(n_machines: int) -> int:
        return n_machines * 4

    def observation_with_actions(self, modes: Iterable[int]) -> np.ndarray:
        return np.concatenate([self.observation(), encode_modes(modes, self.n_machines)])

    # ------------------------------------------------------------------
    # Dynamics
    # ------------------------------------------------------------------
    def step(self, modes: Iterable[int]) -> tuple[np.ndarray, float, bool, PlantInfo]:
        assert self.state is not None
        s = self.state
        modes_arr = np.asarray(list(modes), dtype=int)
        if modes_arr.shape != (self.n_machines,):
            raise ValueError(f"expected {self.n_machines} modes, got {modes_arr.shape}")
        if np.any((modes_arr < 0) | (modes_arr >= len(MODE_NAMES))):
            raise ValueError("invalid machine mode")
        s.modes = modes_arr

        demand = self.demand(s.hour)
        price = self.energy_price(s.hour)
        loads = LOADS[modes_arr]
        production = np.zeros(self.n_machines)
        energy_cost = 0.0
        maintenance_cost = 0.0
        failure_cost = 0.0
        failures = 0
        maintenances = 0
        downtime_count = 0.0

        for i, spec in enumerate(self.specs):
            mode = int(modes_arr[i])
            if s.down_remaining[i] > 0.0:
                # A maintenance request on a failed machine is an expedited repair:
                # it removes two hours from the remaining downtime and restores a
                # minimum healthy state when the repair completes.
                if mode == MODE_MAINTENANCE:
                    s.down_remaining[i] = max(0.0, s.down_remaining[i] - 2.0)
                    maintenance_cost += 0.45 * spec.repair_cost
                    if s.down_remaining[i] <= 0.0:
                        s.health[i] = max(float(s.health[i]), 0.84)
                        s.age[i] = 0.0
                        maintenances += 1
                else:
                    s.down_remaining[i] = max(0.0, s.down_remaining[i] - 1.0)
                downtime_count += 1.0
                continue

            if s.maintenance_remaining[i] > 0.0:
                s.maintenance_remaining[i] = max(0.0, s.maintenance_remaining[i] - 1.0)
                if s.maintenance_remaining[i] <= 0.0:
                    s.health[i] = 1.0
                    s.age[i] = 0.0
                    s.temperature[i] = self.ambient_temp + 1.0
                    s.vibration[i] = 0.12
                continue

            if mode == MODE_MAINTENANCE:
                if s.health[i] < 0.995:
                    s.maintenance_remaining[i] = 2.0
                    maintenance_cost += spec.maintenance_cost
                    maintenances += 1
                continue

            load = float(loads[i])
            if load <= 0.0:
                target_temp = self.ambient_temp
            else:
                target_temp = self.ambient_temp + spec.temp_gain * load * (1.0 + 0.35 * (1.0 - s.health[i]))
            tau = 3.2
            s.temperature[i] += (target_temp - s.temperature[i]) / tau
            s.temperature[i] += self._rng.normal(0.0, 0.18)

            s.vibration[i] = float(
                np.clip(
                    0.08 + 0.34 * load + 0.28 * (1.0 - s.health[i]) + self._rng.normal(0.0, 0.012),
                    0.0,
                    1.0,
                )
            )
            temp_stress = max(0.0, s.temperature[i] - (self.ambient_temp + 18.0)) / 18.0
            deg = (
                spec.base_degradation
                * (load ** 1.45)
                * (1.0 + 2.6 * (1.0 - s.health[i]) ** 1.35)
                * (1.0 + 0.55 * temp_stress)
            )
            s.health[i] = float(np.clip(s.health[i] - deg + self._rng.normal(0.0, 0.00018), 0.02, 1.0))
            s.age[i] += 1.0

            health_risk = max(0.0, 0.62 - s.health[i]) ** 3
            p_failure = np.clip(
                0.0012
                + 0.14 * health_risk
                + 0.045 * max(0.0, temp_stress)
                + 0.012 * max(0.0, s.vibration[i] - 0.68)
                + 0.0018 * load,
                0.0,
                0.24,
            )
            if self._rng.random() < p_failure:
                failures += 1
                failure_cost += spec.repair_cost
                s.down_remaining[i] = float(self._rng.integers(4, 13))
                s.health[i] = float(np.clip(s.health[i] - self._rng.uniform(0.10, 0.24), 0.02, 1.0))
                continue

            availability = 1.0 if s.health[i] > 0.08 else 0.0
            production[i] = spec.capacity * load * (0.78 + 0.22 * s.health[i]) * availability
            energy_cost += spec.power_full * load * price

        total_production = float(production.sum())
        fulfilled = min(total_production, demand)
        unmet = max(0.0, demand - total_production)
        revenue = fulfilled * self.product_price
        unmet_penalty = unmet * self.product_price * self.unmet_penalty_multiplier
        downtime_penalty = downtime_count * self.downtime_hourly_penalty
        profit = revenue - energy_cost - maintenance_cost - failure_cost - downtime_penalty - unmet_penalty

        s.total_produced += total_production
        s.cumulative_profit += profit
        s.cumulative_unmet += unmet
        s.failure_count += failures
        s.maintenance_count += maintenances
        s.downtime_hours += downtime_count
        s.hour += 1

        capacity = float(np.sum([spec.capacity * (0.78 + 0.22 * s.health[i]) for i, spec in enumerate(self.specs)]))
        risk_score = float(np.mean(np.maximum(0.0, 0.65 - s.health) ** 2)) if self.n_machines else 0.0
        info = PlantInfo(
            production=total_production,
            fulfilled=float(fulfilled),
            unmet=float(unmet),
            energy_cost=float(energy_cost),
            maintenance_cost=float(maintenance_cost),
            failure_cost=float(failure_cost),
            downtime_penalty=float(downtime_penalty),
            unmet_penalty=float(unmet_penalty),
            revenue=float(revenue),
            profit=float(profit),
            failures=int(failures),
            maintenances=int(maintenances),
            downtime_count=float(downtime_count),
            capacity_margin=float(capacity - demand),
            risk_score=risk_score,
            modes=modes_arr.copy(),
        )
        done = s.hour >= self.episode_hours
        return self.observation(), float(profit), done, info


def encode_modes(modes: Iterable[int], n_machines: int) -> np.ndarray:
    arr = np.asarray(list(modes), dtype=int)
    if arr.shape != (n_machines,):
        raise ValueError(f"expected {n_machines} modes")
    out = np.zeros((n_machines, 4), dtype=float)
    out[np.arange(n_machines), np.clip(arr, 0, 3)] = 1.0
    return out.reshape(-1)


def decode_action_vector(action: Iterable[float] | np.ndarray, n_machines: int) -> np.ndarray:
    """Decode either one-hot logits/actions or direct integer mode indices."""
    arr = np.asarray(action, dtype=float)
    if arr.shape == (n_machines,):
        return np.clip(np.rint(arr), 0, 3).astype(int)
    if arr.size == n_machines * 4:
        return np.argmax(arr.reshape(n_machines, 4), axis=1).astype(int)
    raise ValueError(f"action has unsupported shape {arr.shape}")


def safe_capacity_action(machine_indices: Iterable[int], n_machines: int, mode: int = MODE_MAINTENANCE) -> np.ndarray:
    modes = np.full(n_machines, MODE_FULL, dtype=int)
    for idx in machine_indices:
        modes[int(idx)] = mode
    return modes

