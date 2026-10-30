"""Transition data collection for the action-conditioned world model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np

from .plant import MODE_DERATE, MODE_FULL, MODE_MAINTENANCE, MODE_OFF, ProductionPlant, encode_modes


Policy = Callable[[ProductionPlant, np.random.Generator], np.ndarray]


def random_policy(plant: ProductionPlant, rng: np.random.Generator) -> np.ndarray:
    # Bias towards production but preserve enough maintenance/offline exploration.
    probs = np.array([0.10, 0.18, 0.58, 0.14])
    return rng.choice(4, size=plant.n_machines, p=probs)


def threshold_policy(plant: ProductionPlant, rng: np.random.Generator) -> np.ndarray:
    """A strong hand-coded baseline used to cover maintenance transitions."""
    assert plant.state is not None
    modes = np.full(plant.n_machines, MODE_FULL, dtype=int)
    for i in range(plant.n_machines):
        if plant.state.health[i] < 0.48 or plant.state.temperature[i] > plant.ambient_temp + 24.0:
            modes[i] = MODE_MAINTENANCE
        elif plant.state.health[i] < 0.68:
            modes[i] = MODE_DERATE
    return modes


def mixed_policy(plant: ProductionPlant, rng: np.random.Generator) -> np.ndarray:
    if rng.random() < 0.45:
        return threshold_policy(plant, rng)
    return random_policy(plant, rng)


@dataclass
class TransitionDataset:
    states: np.ndarray
    actions: np.ndarray
    next_states: np.ndarray
    profits: np.ndarray
    productions: np.ndarray
    seed: int

    @property
    def n_samples(self) -> int:
        return int(self.states.shape[0])

    def split(self, val_fraction: float = 0.15, seed: int = 0) -> tuple["TransitionDataset", "TransitionDataset"]:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(self.n_samples)
        n_val = max(1, int(round(self.n_samples * val_fraction)))
        val_idx, train_idx = idx[:n_val], idx[n_val:]
        return self._subset(train_idx), self._subset(val_idx)

    def _subset(self, idx: np.ndarray) -> "TransitionDataset":
        return TransitionDataset(
            states=self.states[idx],
            actions=self.actions[idx],
            next_states=self.next_states[idx],
            profits=self.profits[idx],
            productions=self.productions[idx],
            seed=self.seed,
        )


def collect_transitions(
    n_episodes: int = 120,
    episode_hours: int = 168,
    seed: int = 20261008,
    policy: Policy = mixed_policy,
) -> TransitionDataset:
    rng = np.random.default_rng(seed)
    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    next_states: list[np.ndarray] = []
    profits: list[float] = []
    productions: list[float] = []

    for ep in range(n_episodes):
        plant = ProductionPlant(seed=int(seed + ep * 17), episode_hours=episode_hours)
        plant.reset(seed=int(seed + ep * 17))
        for _ in range(episode_hours):
            obs = plant.observation()
            mode = np.asarray(policy(plant, rng), dtype=int)
            action = encode_modes(mode, plant.n_machines)
            next_obs, profit, done, info = plant.step(mode)
            states.append(obs)
            actions.append(action)
            next_states.append(next_obs)
            profits.append(profit)
            productions.append(info.production)
            if done:
                break
    return TransitionDataset(
        states=np.asarray(states, dtype=float),
        actions=np.asarray(actions, dtype=float),
        next_states=np.asarray(next_states, dtype=float),
        profits=np.asarray(profits, dtype=float),
        productions=np.asarray(productions, dtype=float),
        seed=int(seed),
    )
