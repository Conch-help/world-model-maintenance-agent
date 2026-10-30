"""Experimental sequence world model for the maintenance agent.

The production planner continues to use the validated ensemble MLP. This module
provides a controlled LSTM comparison so a sequence model is only adopted when
it improves held-out error.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from .data import mixed_policy
from .plant import ProductionPlant, encode_modes


def collect_sequences(n_episodes: int = 40, hours: int = 96, seed: int = 20261008, seq_len: int = 12) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for ep in range(n_episodes):
        plant = ProductionPlant(seed=seed + ep * 31, episode_hours=hours)
        obs_seq: list[np.ndarray] = []
        action_seq: list[np.ndarray] = []
        next_machine: list[np.ndarray] = []
        productions: list[float] = []
        profits: list[float] = []
        for _ in range(hours):
            obs = plant.observation()
            mode = np.asarray(mixed_policy(plant, rng), dtype=int)
            obs_seq.append(obs)
            action_seq.append(encode_modes(mode, plant.n_machines))
            next_obs, profit, _, info = plant.step(mode)
            next_machine.append(next_obs[: plant.n_machines * 5])
            productions.append(info.production)
            profits.append(profit)
        x = np.concatenate([np.asarray(obs_seq), np.asarray(action_seq)], axis=1)
        y = np.concatenate([
            np.asarray(next_machine),
            (np.asarray(productions) / 200.0).reshape(-1, 1),
            (np.asarray(profits) / 1500.0).reshape(-1, 1),
        ], axis=1)
        for start in range(0, len(x) - seq_len + 1, seq_len):
            xs.append(x[start:start + seq_len])
            ys.append(y[start:start + seq_len])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


@dataclass
class SequenceMetrics:
    health_rmse: float
    machine_state_rmse: float
    profit_mae: float
    one_step_loss: float


def train_and_evaluate_sequence_model(
    output_path: str | Path,
    n_episodes: int = 40,
    hours: int = 96,
    seq_len: int = 12,
    epochs: int = 25,
    seed: int = 20261008,
) -> dict:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    x, y = collect_sequences(n_episodes=n_episodes, hours=hours, seed=seed, seq_len=seq_len)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(x))
    n_val = max(1, int(len(x) * 0.2))
    val_idx, train_idx = order[:n_val], order[n_val:]
    x_train, y_train = x[train_idx], y[train_idx]
    x_val, y_val = x[val_idx], y[val_idx]
    x_mean, x_std = x_train.mean(axis=(0, 1), keepdims=True), x_train.std(axis=(0, 1), keepdims=True) + 1e-6
    y_mean, y_std = y_train.mean(axis=(0, 1), keepdims=True), y_train.std(axis=(0, 1), keepdims=True) + 1e-6
    xt = torch.tensor((x_train - x_mean) / x_std)
    yt = torch.tensor((y_train - y_mean) / y_std)
    xv = torch.tensor((x_val - x_mean) / x_std)
    yv = torch.tensor((y_val - y_mean) / y_std)

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(xt.shape[-1], 64, batch_first=True)
            self.head = nn.Linear(64, yt.shape[-1])
        def forward(self, value):
            out, _ = self.lstm(value)
            return self.head(out)

    model = Net()
    optim = torch.optim.Adam(model.parameters(), lr=2e-3)
    loss_fn = nn.MSELoss()
    batch = 64
    for _ in range(epochs):
        perm = torch.randperm(len(xt))
        for start in range(0, len(xt), batch):
            idx = perm[start:start + batch]
            optim.zero_grad()
            loss = loss_fn(model(xt[idx]), yt[idx])
            loss.backward()
            optim.step()
    with torch.no_grad():
        pred_norm = model(xv)
        pred = pred_norm.numpy() * y_std + y_mean
        target = yv.numpy() * y_std + y_mean
    n_machine = 15
    health_idx = np.arange(0, n_machine, 5)
    result = {
        "model": "sequence-lstm-experiment",
        "sequence_length": seq_len,
        "train_sequences": int(len(train_idx)),
        "validation_sequences": int(len(val_idx)),
        "health_rmse": float(np.sqrt(np.mean((pred[..., health_idx] - target[..., health_idx]) ** 2))),
        "machine_state_rmse": float(np.sqrt(np.mean((pred[..., :n_machine] - target[..., :n_machine]) ** 2))),
        "profit_mae": float(np.mean(np.abs(pred[..., -1] - target[..., -1])) * 1500.0),
        "one_step_loss": float(np.mean((pred_norm.numpy() - yv.numpy()) ** 2)),
        "boundary": "Experimental comparison only; the production planner retains the validated ensemble model.",
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    torch.save({"state_dict": model.state_dict(), "x_mean": x_mean, "x_std": x_std, "y_mean": y_mean, "y_std": y_std}, output.with_suffix(".pt"))
    return result
