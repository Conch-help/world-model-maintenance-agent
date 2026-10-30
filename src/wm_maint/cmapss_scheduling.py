"""C-MAPSS scheduling comparison on real degradation trajectories.

This is deliberately different from RUL prediction validation: it evaluates
maintenance timing policies along the public C-MAPSS test trajectories. The
counterfactual maintenance reset is explicitly modelled and documented.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+", header=None)


def _features(group: pd.DataFrame, sensor_cols: list[int]) -> np.ndarray:
    sensors = group.iloc[:, sensor_cols].astype(float)
    roll_mean = sensors.rolling(10, min_periods=1).mean()
    roll_std = sensors.rolling(10, min_periods=1).std().fillna(0.0)
    return np.concatenate([sensors.to_numpy(), roll_mean.to_numpy(), roll_std.to_numpy()], axis=1)


def _fit_predictor(train: pd.DataFrame, sensor_cols: list[int], seed: int) -> tuple[StandardScaler, HistGradientBoostingRegressor]:
    xs, ys = [], []
    for unit, group in train.groupby(0):
        group = group.sort_values(1)
        f = _features(group, sensor_cols)
        age = np.arange(len(group))
        rul = np.minimum(125.0, len(group) - age)
        xs.append(f)
        ys.append(rul)
    x = np.vstack(xs)
    y = np.concatenate(ys)
    scaler = StandardScaler().fit(x)
    model = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, random_state=seed)
    model.fit(scaler.transform(x), y)
    return scaler, model


def _test_trajectories(test: pd.DataFrame, final_rul: np.ndarray, sensor_cols: list[int]) -> list[dict]:
    out = []
    for idx, (unit, group) in enumerate(test.groupby(0)):
        group = group.sort_values(1)
        out.append({
            "unit": int(unit),
            "features": _features(group, sensor_cols),
            "final_rul": float(final_rul[idx]),
            "length": int(len(group)),
        })
    return out


def _true_rul(traj: dict, pos: int) -> float:
    if pos < traj["length"]:
        return float((traj["length"] - pos - 1) + traj["final_rul"])
    return max(0.0, traj["final_rul"] - (pos - traj["length"] + 1))


def _simulate(
    trajectories: list[dict],
    predicted_rul: dict[int, np.ndarray],
    policy_name: str,
    decision: Callable[[dict, int, float], bool],
    horizon: int = 250,
    maintenance_cost: float = 80.0,
    failure_cost: float = 800.0,
    operating_cost: float = 1.0,
) -> dict[str, float]:
    costs = []
    failures = []
    maintenances = []
    availability = []
    for traj in trajectories:
        pos = 0
        total_cost = 0.0
        n_failures = 0
        n_maint = 0
        available_hours = 0
        pred = predicted_rul[traj["unit"]]
        for step in range(horizon):
            rul = _true_rul(traj, pos)
            if rul <= 0.0:
                n_failures += 1
                total_cost += failure_cost
                pos = 0
                continue
            if decision(traj, pos, float(pred[min(pos, len(pred) - 1)])):
                n_maint += 1
                total_cost += maintenance_cost
                pos = 0
                continue
            total_cost += operating_cost
            available_hours += 1
            pos += 1
        costs.append(total_cost)
        failures.append(n_failures)
        maintenances.append(n_maint)
        availability.append(available_hours / horizon)
    return {
        "policy": policy_name,
        "mean_cost": float(np.mean(costs)),
        "mean_failures": float(np.mean(failures)),
        "mean_maintenances": float(np.mean(maintenances)),
        "availability": float(np.mean(availability)),
        "n_units": len(trajectories),
    }


def run_cmapss_scheduling(data_root: str | Path, output_path: str | Path, seed: int = 20261008) -> dict:
    root = Path(data_root) / "CMAPSS"
    train = _load(root / "train_FD001.txt")
    test = _load(root / "test_FD001.txt")
    final_rul = _load(root / "RUL_FD001.txt").iloc[:, 0].to_numpy(dtype=float)
    sensor_cols = list(range(2, 26))
    scaler, model = _fit_predictor(train, sensor_cols, seed)
    trajectories = _test_trajectories(test, final_rul, sensor_cols)
    predicted = {
        traj["unit"]: model.predict(scaler.transform(traj["features"]))
        for traj in trajectories
    }

    policies = {
        "no_maintenance": lambda traj, pos, pred_rul: False,
        "fixed_interval_50": lambda traj, pos, pred_rul: pos > 0 and pos % 50 == 0,
        "oracle_rul_20": lambda traj, pos, pred_rul: _true_rul(traj, pos) <= 20.0,
        "predicted_rul_20": lambda traj, pos, pred_rul: pred_rul <= 20.0,
        "predicted_rul_35": lambda traj, pos, pred_rul: pred_rul <= 35.0,
        "predicted_rul_50": lambda traj, pos, pred_rul: pred_rul <= 50.0,
    }
    rows = [_simulate(trajectories, predicted, name, fn) for name, fn in policies.items()]
    baseline = next(row for row in rows if row["policy"] == "threshold" or row["policy"] == "predicted_rul_35")
    for row in rows:
        row["cost_vs_predicted_35_pct"] = (row["mean_cost"] - baseline["mean_cost"]) / max(1.0, abs(baseline["mean_cost"])) * 100.0
    report = {
        "dataset": "NASA C-MAPSS FD001",
        "mode": "scheduling comparison on real degradation trajectories",
        "counterfactual_assumption": "Maintenance resets the unit to its first observed trajectory state and incurs a fixed cost.",
        "horizon_cycles": 250,
        "maintenance_cost": 80.0,
        "failure_cost": 800.0,
        "operating_cost": 1.0,
        "policies": rows,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
