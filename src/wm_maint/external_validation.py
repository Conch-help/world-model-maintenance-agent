"""External validation against the public NASA C-MAPSS turbofan benchmark."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _window_features(windows) -> "list[float]":
    import numpy as np

    arr = np.asarray(windows, dtype=float)
    return np.concatenate([arr.mean(axis=1), arr.std(axis=1), arr[:, -1, :]], axis=1)


def validate_cmapss(data_root: str | Path, output_path: str | Path, fd: int = 1, seed: int = 20261008) -> dict[str, Any]:
    """Train and evaluate a public C-MAPSS RUL baseline.

    This is an external, publicly available dataset check of the health/RUL
    signal. It does not pretend to validate the plant-specific scheduling
    economics; that boundary is recorded in the report.
    """
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    # Set the package's root before importing it. Its class-level path is frozen
    # at import time, so setting the environment first is required for isolation.
    data_root = Path(data_root).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ["RUL_DATASETS_DATA_ROOT"] = str(data_root)
    import rul_datasets  # type: ignore

    reader = rul_datasets.CmapssReader(fd=int(fd), window_size=30)
    reader.prepare_data()
    splits = {name: reader.load_split(name) for name in ("dev", "val", "test")}
    x_dev = np.vstack([_window_features(x) for x in splits["dev"][0]])
    y_dev = np.concatenate(splits["dev"][1])
    x_val = np.vstack([_window_features(x) for x in splits["val"][0]])
    y_val = np.concatenate(splits["val"][1])
    x_test = np.vstack([_window_features(x) for x in splits["test"][0]])
    y_test = np.concatenate(splits["test"][1])
    x_train = np.vstack([x_dev, x_val])
    y_train = np.concatenate([y_dev, y_val])

    models = {
        "mean_baseline": None,
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=seed, n_jobs=-1),
        "hist_gradient_boosting": HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=seed),
    }
    results: dict[str, Any] = {
        "dataset": "NASA C-MAPSS FD001",
        "source": "NASA PCoE Turbofan Engine Degradation Simulation Data Set",
        "fd": int(fd),
        "window_size": 30,
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "metrics": {},
        "boundary": "External RUL benchmark only; it does not replace plant-specific scheduling validation.",
    }
    mean_pred = np.full_like(y_test, float(np.mean(y_train)), dtype=float)
    results["metrics"]["mean_baseline"] = _metrics(y_test, mean_pred, mean_absolute_error, mean_squared_error, r2_score)
    for name, model in models.items():
        if model is None:
            continue
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        results["metrics"][name] = _metrics(y_test, pred, mean_absolute_error, mean_squared_error, r2_score)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def _metrics(y_true, y_pred, mae_fn, mse_fn, r2_fn) -> dict[str, float]:
    import numpy as np

    rmse = float(np.sqrt(mse_fn(y_true, y_pred)))
    return {
        "mae": float(mae_fn(y_true, y_pred)),
        "rmse": rmse,
        "r2": float(r2_fn(y_true, y_pred)),
        "within_10_cycles_pct": float(np.mean(np.abs(y_true - y_pred) <= 10.0) * 100.0),
        "within_20_cycles_pct": float(np.mean(np.abs(y_true - y_pred) <= 20.0) * 100.0),
    }
