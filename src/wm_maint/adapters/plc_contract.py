"""PLC/DCS integration contract for the maintenance agent.

This module defines a safety-oriented adapter boundary. It does not claim a
physical PLC was available during development. A real deployment must map the
same contract to the site's OPC UA, Modbus TCP or gateway implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from ..plant import MODE_DERATE, MODE_FULL, MODE_MAINTENANCE, MODE_OFF


@dataclass
class PLCStateFrame:
    machine_health: list[float]
    machine_temperature_c: list[float]
    machine_vibration: list[float]
    demand_units_h: float
    energy_price: float
    emergency_stop: bool = False
    maintenance_permission: bool = True
    watchdog_ok: bool = True


@dataclass
class PLCCommandFrame:
    modes: list[int]
    approval_id: str
    trace_id: str
    max_execution_hours: int = 1
    require_permission: bool = True


@dataclass
class PLCValidation:
    accepted: bool
    reasons: list[str] = field(default_factory=list)


def validate_command(
    state: PLCStateFrame,
    command: PLCCommandFrame,
    *,
    allowed_modes: Iterable[int] = (MODE_OFF, MODE_DERATE, MODE_FULL, MODE_MAINTENANCE),
) -> PLCValidation:
    """Validate a command before it reaches a real controller."""
    reasons: list[str] = []
    if state.emergency_stop:
        reasons.append("emergency_stop_active")
    if command.require_permission and not state.maintenance_permission:
        reasons.append("maintenance_permission_missing")
    if not state.watchdog_ok:
        reasons.append("watchdog_not_ok")
    if not command.approval_id:
        reasons.append("approval_id_missing")
    if not command.trace_id:
        reasons.append("trace_id_missing")
    if any(mode not in set(allowed_modes) for mode in command.modes):
        reasons.append("mode_not_allowed")
    if command.max_execution_hours < 1 or command.max_execution_hours > 4:
        reasons.append("execution_budget_out_of_range")
    return PLCValidation(accepted=not reasons, reasons=reasons)


def modes_to_coils(modes: Iterable[int]) -> list[bool]:
    """Encode maintenance requests as read/write coils.

    Coils are only requests. The real controller remains responsible for
    interlocks, emergency stop and safe actuation.
    """
    requested = np.asarray(list(modes), dtype=int)
    return [bool(m == MODE_MAINTENANCE) for m in requested]


def state_to_registers(state: PLCStateFrame) -> list[float]:
    """Flatten a state frame into a stable register ordering."""
    return [
        *state.machine_health,
        *state.machine_temperature_c,
        *state.machine_vibration,
        state.demand_units_h,
        state.energy_price,
        1.0 if state.emergency_stop else 0.0,
        1.0 if state.maintenance_permission else 0.0,
        1.0 if state.watchdog_ok else 0.0,
    ]


class InMemoryPLC:
    """Test double for the adapter contract; never used as a real controller."""

    def __init__(self) -> None:
        self.state = PLCStateFrame(
            machine_health=[1.0, 1.0, 1.0],
            machine_temperature_c=[30.0, 30.0, 30.0],
            machine_vibration=[0.1, 0.1, 0.1],
            demand_units_h=60.0,
            energy_price=0.12,
        )
        self.last_command: PLCCommandFrame | None = None
        self.audit: list[PLCValidation] = []

    def write(self, command: PLCCommandFrame) -> PLCValidation:
        validation = validate_command(self.state, command)
        self.audit.append(validation)
        if validation.accepted:
            self.last_command = command
        return validation
