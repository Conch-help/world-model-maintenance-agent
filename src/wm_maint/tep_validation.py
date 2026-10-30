"""Tennessee Eastman Process external validation.

The TEP data is a public chemical-process simulation benchmark. It is used
here for external fault-detection and fault-type validation, not as a real
production DCS dataset.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

import numpy as np
import pandas as pd


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    time_col = df.columns[0]
    return df.drop(columns=[time_col])


def _file_feature(df: pd.DataFrame, sample_step: int = 10) -> np.ndarray:
    arr = df.iloc[::sample_step].to_numpy(dtype=float)
    return np.concatenate([arr.mean(axis=0), arr.std(axis=0), arr.min(axis=0), arr.max(axis=0)])


def _windowed_max_z(df: pd.DataFrame, mean: np.ndarray, std: np.ndarray, sample_step: int = 10, window: int = 20) -> float:
    arr = df.iloc[::sample_step].to_numpy(dtype=float)
    z = np.abs((arr - mean) / std)
    # A fault is detected if any short window contains a sustained deviation.
    if len(z) < window:
        return float(np.max(z))
    rolling = np.array([np.mean(z[i:i + window]) for i in range(0, len(z) - window + 1, max(1, window // 2))])
    return float(np.max(rolling)) if len(rolling) else float(np.max(z))


def run_tep_validation(data_root: str | Path, output_path: str | Path) -> dict:
    root = Path(data_root) / "tennessee-eastman-dataset" / "simulations" / "mode_1"
    normal_500 = _read(root / "mode1_normal_500.xlsx")
    normal_50 = _read(root / "mode1_normal_50.xlsx")
    normal_train = normal_500.iloc[: len(normal_500) // 2]
    normal_holdout = normal_500.iloc[len(normal_500) // 2 :]
    mean = normal_train.mean(axis=0).to_numpy(dtype=float)
    std = normal_train.std(axis=0).to_numpy(dtype=float) + 1e-9

    # Normal threshold from held-out normal windows.
    normal_scores = [
        _windowed_max_z(normal_holdout.iloc[i:i + 200], mean, std)
        for i in range(0, max(1, len(normal_holdout) - 200), 100)
    ]
    threshold = float(np.percentile(normal_scores, 99.0))
    normal_false_positive = float(np.mean(np.asarray(normal_scores) > threshold))

    fault_files: dict[int, list[Path]] = {}
    for path in sorted((root / "faults").glob("mode1_*.xlsx")):
        match = re.match(r"mode1_(\d+)_(\d+)\.xlsx$", path.name)
        if match:
            fault_files.setdefault(int(match.group(1)), []).append(path)
    fault_detection: dict[str, float] = {}
    score_rows: dict[int, list[float]] = {}
    for fault, paths in sorted(fault_files.items()):
        scores = [_windowed_max_z(_read(path), mean, std) for path in paths[:5]]
        score_rows[fault] = scores
        fault_detection[str(fault)] = float(np.mean(np.asarray(scores) > threshold))

    # Fault-type classification on held-out batches using per-file centroids.
    train_centroids: dict[int, np.ndarray] = {}
    feature_mean = _file_feature(normal_500, sample_step=20)
    for fault, paths in sorted(fault_files.items()):
        train_features = [_file_feature(_read(path), sample_step=20) for path in paths[:5]]
        train_centroids[fault] = np.mean(train_features, axis=0)
    global_scale = np.std(np.stack(list(train_centroids.values())), axis=0) + 1e-9
    correct = 0
    total = 0
    confusion: dict[str, dict[str, int]] = {}
    for fault, paths in sorted(fault_files.items()):
        for path in paths[5:10]:
            vec = _file_feature(_read(path), sample_step=20)
            distances = {label: float(np.linalg.norm((vec - center) / global_scale)) for label, center in train_centroids.items()}
            predicted = min(distances, key=distances.get)
            total += 1
            correct += int(predicted == fault)
            confusion.setdefault(str(fault), {}).setdefault(str(predicted), 0)
            confusion[str(fault)][str(predicted)] += 1

    report = {
        "dataset": "Tennessee Eastman Process Mode 1",
        "source": "Blound04/tennessee-eastman-dataset (MIT), based on the original TEP benchmark",
        "mode": "external fault detection and fault-type validation",
        "normal_training_hours": len(normal_train) / len(normal_500) * 500.0,
        "normal_holdout_hours": len(normal_holdout) / len(normal_500) * 500.0,
        "anomaly_threshold": threshold,
        "normal_false_positive_rate": normal_false_positive,
        "fault_detection_rate_by_fault": fault_detection,
        "fault_detection_rate_mean": float(np.mean(list(fault_detection.values()))),
        "fault_detection_rate_min": float(np.min(list(fault_detection.values()))),
        "fault_type_accuracy": float(correct / max(1, total)),
        "fault_type_n_test": total,
        "fault_type_confusion": confusion,
        "boundary": "TEP is a public simulation benchmark, not a real production DCS dataset.",
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
