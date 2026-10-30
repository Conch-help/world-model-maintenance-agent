"""Configuration and reproducibility utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load a JSON config, falling back to the bundled default."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class MachineSpec:
    capacity: float
    base_degradation: float
    temp_gain: float
    failure_sensitivity: float
    power_full: float
    maintenance_cost: float
    repair_cost: float


def default_machine_specs(n: int = 3) -> tuple[MachineSpec, ...]:
    """Three deliberately heterogeneous machines.

    Heterogeneity makes the scheduling problem non-trivial: the same action has
    different cost, degradation and capacity effects on each machine.
    """
    base = [
        MachineSpec(38.0, 0.00105, 34.0, 1.00, 19.0, 420.0, 4800.0),
        MachineSpec(31.0, 0.00130, 39.0, 1.18, 17.0, 360.0, 4300.0),
        MachineSpec(27.0, 0.00088, 31.0, 0.86, 14.0, 310.0, 3900.0),
    ]
    if n <= len(base):
        return tuple(base[:n])
    return tuple(base + [base[-1]] * (n - len(base)))
