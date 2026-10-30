"""Schema adapter for authorized DAYPSCI v1 PLC testbed data.

No DAYPSCI dataset is bundled because no verifiable public source and license
were found. This adapter makes the expected schema explicit and fails closed
until the user supplies an authorized file.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class DAYPSCIValidation:
    valid: bool
    reasons: list[str]
    n_rows: int = 0
    n_signals: int = 0
    fault_rate: float = 0.0
    summary: dict[str, Any] | None = None


def validate_frame(df: pd.DataFrame) -> DAYPSCIValidation:
    reasons: list[str] = []
    lower = {str(c).lower(): c for c in df.columns}
    time_key = next((k for k in ('timestamp', 'time', 'datetime') if k in lower), None)
    if time_key is None:
        reasons.append('missing timestamp/time column')
    label_key = next((k for k in ('fault_label', 'fault', 'label', 'anomaly') if k in lower), None)
    active_key = next((k for k in ('fault_active', 'active_fault', 'is_fault') if k in lower), None)
    if label_key is None and active_key is None:
        reasons.append('missing fault label/active flag')
    numeric = df.select_dtypes(include=[np.number])
    label_col = lower.get(label_key) if label_key else None
    active_col = lower.get(active_key) if active_key else None
    # Exclude label columns from the signal count.
    time_col = lower.get(time_key) if time_key else None
    signal_cols = [c for c in numeric.columns if c not in {time_col, label_col, active_col}]
    if len(signal_cols) < 2:
        reasons.append('need at least two numeric PLC signal columns')
    fault_rate = 0.0
    if active_col is not None:
        fault_rate = float(pd.to_numeric(df[active_col], errors='coerce').fillna(0).astype(float).gt(0).mean())
    elif label_col is not None:
        vals = df[label_col].astype(str).str.lower()
        fault_rate = float((~vals.isin({'normal', 'good', '0', 'false', 'none'})).mean())
    summary = {
        'timestamp_column': lower.get(time_key) if time_key else None,
        'label_column': lower.get(label_key) if label_key else None,
        'active_column': lower.get(active_key) if active_key else None,
        'signal_columns': [str(c) for c in signal_cols],
        'signal_means': {str(c): float(pd.to_numeric(df[c], errors='coerce').mean()) for c in signal_cols},
    }
    return DAYPSCIValidation(not reasons, reasons, len(df), len(signal_cols), fault_rate, summary)


def load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def validate_file(path: str | Path) -> DAYPSCIValidation:
    return validate_frame(load_csv(path))
