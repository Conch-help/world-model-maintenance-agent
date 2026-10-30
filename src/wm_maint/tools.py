"""Stateful MCP tools for the maintenance agent.

The tool layer is deliberately independent from the reference plant and world
model. Every state-changing action is approval-gated and appended to a
hash-chained trace ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

import numpy as np

from .config import PROJECT_ROOT, load_config
from .evaluation import WorldModelPolicy
from .plant import MODE_FULL, MODE_MAINTENANCE, MODE_NAMES, PlantInfo, ProductionPlant, encode_modes
from .planner import CEMPlanner, Plan, safety_shield, verify_plan
from .world_model import EnsembleWorldModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(payload: dict[str, Any], previous: str) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(previous.encode("ascii") + blob).hexdigest()


class TraceLedger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.last_hash = "GENESIS"

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "seq": len(self.events) + 1,
            "time": _now(),
            "type": event_type,
            "payload": payload,
            "prev_hash": self.last_hash,
        }
        record["hash"] = _digest(record, self.last_hash)
        self.last_hash = record["hash"]
        self.events.append(record)
        return record

    def verify(self) -> bool:
        prev = "GENESIS"
        for record in self.events:
            copy = dict(record)
            actual = copy.pop("hash")
            expected = _digest(copy, prev)
            if copy["prev_hash"] != prev or actual != expected:
                return False
            prev = actual
        return True


@dataclass
class CalibrationState:
    n_runs: int = 0
    actual_profit_sum: float = 0.0
    verified_profit_sum: float = 0.0
    actual_failures: int = 0
    verified_failures: int = 0
    shield_adjustments: int = 0

    @property
    def profit_scale(self) -> float:
        if self.verified_profit_sum <= 0.0 or self.n_runs == 0:
            return 1.0
        return self.actual_profit_sum / self.verified_profit_sum

    def summary(self) -> dict[str, Any]:
        return {
            "n_runs": self.n_runs,
            "profit_scale": round(float(self.profit_scale), 4),
            "actual_profit_mean": round(self.actual_profit_sum / self.n_runs, 2) if self.n_runs else 0.0,
            "verified_profit_mean": round(self.verified_profit_sum / self.n_runs, 2) if self.n_runs else 0.0,
            "actual_failures_mean": round(self.actual_failures / self.n_runs, 3) if self.n_runs else 0.0,
            "verified_failures_mean": round(self.verified_failures / self.n_runs, 3) if self.n_runs else 0.0,
            "failure_bias": round(self.actual_failures / self.n_runs - self.verified_failures / self.n_runs, 3) if self.n_runs else 0.0,
            "shield_adjustments": self.shield_adjustments,
        }


@dataclass
class StoredPlan:
    plan_id: str
    created_at: str
    horizon: int
    modes: list[list[int]]
    predicted_profit: float
    predicted_risk: float
    verification: dict[str, Any] | None = None
    executed_steps: int = 0
    executed_indices: list[int] = field(default_factory=list)


class MaintenanceAgent:
    """High-level, human-in-the-loop maintenance decision agent."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        config_path: str | Path | None = None,
        seed: int = 20261008,
    ) -> None:
        self.cfg = load_config(config_path)
        self.model_path = Path(model_path) if model_path else PROJECT_ROOT / "artifacts" / "world_model.npz"
        if not self.model_path.exists():
            raise FileNotFoundError(f"world model not found: {self.model_path}")
        self.model = EnsembleWorldModel.load(self.model_path)
        self.plant = ProductionPlant(
            seed=int(seed),
            episode_hours=int(self.cfg["plant"]["episode_hours"]),
        )
        planner_cfg = self.cfg["planner"]
        self.planner = CEMPlanner(
            horizon=int(planner_cfg["horizon"]),
            population=int(planner_cfg["population"]),
            elite=int(planner_cfg["elite"]),
            iterations=int(planner_cfg["iterations"]),
            seed=int(seed),
        )
        self.plans: dict[str, StoredPlan] = {}
        self.calibration = CalibrationState()
        self.trace = TraceLedger()
        self.trace.append("session/start", {"seed": int(seed), "model_path": str(self.model_path)})

    # ------------------------------------------------------------------
    # Read-only tools
    # ------------------------------------------------------------------
    def plant_read_state(self, **_: Any) -> dict[str, Any]:
        assert self.plant.state is not None
        s = self.plant.state
        payload = {
            "status": "ok",
            "schema": "maintenance-agent/1.0",
            "hour": s.hour,
            "seed": self.plant.seed,
            "machines": [
                {
                    "id": f"M{i + 1}",
                    "health": round(float(s.health[i]), 4),
                    "temperature_c": round(float(s.temperature[i]), 2),
                    "vibration": round(float(s.vibration[i]), 4),
                    "down_remaining_h": round(float(s.down_remaining[i]), 2),
                    "maintenance_remaining_h": round(float(s.maintenance_remaining[i]), 2),
                }
                for i in range(self.plant.n_machines)
            ],
            "demand_units_h": round(self.plant.demand(s.hour), 2),
            "energy_price": round(self.plant.energy_price(s.hour), 4),
            "cumulative_profit": round(float(s.cumulative_profit), 2),
        }
        self.trace.append("tool/plant_read_state", {"hour": s.hour})
        return payload

    def world_model_plan(self, horizon: int | None = None, risk_aware: bool = True, **_: Any) -> dict[str, Any]:
        assert self.plant.state is not None
        if horizon is not None:
            self.planner.horizon = int(horizon)
        plan = self.planner.plan(
            self.model,
            self.plant,
            verify_candidates=4 if bool(risk_aware) else 0,
        )
        plan_id = f"PLAN-{self.plant.seed}-{self.plant.state.hour}"
        stored = StoredPlan(
            plan_id=plan_id,
            created_at=_now(),
            horizon=int(plan.modes.shape[0]),
            modes=plan.modes.astype(int).tolist(),
            predicted_profit=float(plan.predicted_profit),
            predicted_risk=float(plan.predicted_risk),
        )
        self.plans[plan_id] = stored
        self.trace.append(
            "tool/world_model_plan",
            {
                "plan_id": plan_id,
                "hour": self.plant.state.hour,
                "horizon": stored.horizon,
                "predicted_profit": stored.predicted_profit,
                "predicted_risk": stored.predicted_risk,
                "modes": stored.modes,
            },
        )
        return {
            "status": "ok",
            "plan_id": plan_id,
            "hour": self.plant.state.hour,
            "horizon": stored.horizon,
            "predicted_profit": round(stored.predicted_profit, 2),
            "predicted_risk": round(stored.predicted_risk, 6),
            "modes": stored.modes,
            "mode_names": [MODE_NAMES[m] for step in stored.modes for m in step],
            "risk_aware": bool(risk_aware),
            "calibration": self.calibration.summary(),
            "requires_highfidelity_verification": True,
        }

    def highfidelity_verify(self, plan_id: str, n_scenarios: int = 32, **_: Any) -> dict[str, Any]:
        stored = self.plans.get(plan_id)
        if stored is None:
            return {"status": "error", "error": "unknown plan_id"}
        modes = np.asarray(stored.modes, dtype=int)
        scenario_count = max(8, min(128, int(n_scenarios)))
        result = verify_plan(self.plant, modes, scenario_seeds=tuple(7100 + i for i in range(scenario_count)))
        capacity_ok = int(result["capacity_violations"]) == 0
        profit_ok = float(result["profit"]) > 0.0
        all_pass = bool(capacity_ok and profit_ok)
        payload = {
            "status": "ok",
            "plan_id": plan_id,
            "all_pass": all_pass,
            "capacity_ok": capacity_ok,
            "profit_ok": profit_ok,
            "verified_profit": round(float(result["profit"]), 2),
            "verified_failures": int(result["failures"]),
            "verified_unmet": round(float(result["unmet"]), 2),
            "capacity_violations": int(result["capacity_violations"]),
            "risk": round(float(result["risk"]), 6),
            "verified_robust_score": round(float(result["robust_score"]), 2),
            "n_scenarios": scenario_count,
            "profit_p05": round(float(result["profit_p05"]), 2),
            "profit_p50": round(float(result["profit_p50"]), 2),
            "profit_p95": round(float(result["profit_p95"]), 2),
            "profit_cvar10": round(float(result["profit_cvar10"]), 2),
            "failure_probability": round(float(result["failure_probability"]), 4),
            "failures_p50": float(result["failures_p50"]),
            "failures_p90": float(result["failures_p90"]),
            "failures_p95": float(result["failures_p95"]),
            "failures_max": int(result["failures_max"]),
            "unmet_p90": round(float(result["unmet_p90"]), 2),
            "unmet_p95": round(float(result["unmet_p95"]), 2),
            "capacity_violations_max": int(result["capacity_violations_max"]),
        }
        stored.verification = payload
        self.trace.append("tool/highfidelity_verify", payload)
        return payload

    def plan_status(self, plan_id: str, **_: Any) -> dict[str, Any]:
        stored = self.plans.get(plan_id)
        if stored is None:
            return {"status": "error", "error": "unknown plan_id"}
        remaining = [i for i in range(stored.horizon) if i not in stored.executed_indices]
        next_step = remaining[0] if remaining else None
        return {
            "status": "ok",
            "plan_id": plan_id,
            "horizon": stored.horizon,
            "executed_steps": list(stored.executed_indices),
            "remaining_steps": remaining,
            "next_step_index": next_step,
            "next_modes": stored.modes[next_step] if next_step is not None else None,
            "completed": next_step is None,
        }

    # ------------------------------------------------------------------
    # Approval-gated action tool
    # ------------------------------------------------------------------
    def request_maintenance_action(
        self,
        plan_id: str,
        step_index: int = 0,
        approved: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        stored = self.plans.get(plan_id)
        if stored is None:
            return {"status": "error", "error": "unknown plan_id"}
        if int(step_index) < 0 or int(step_index) >= stored.horizon:
            return {"status": "error", "error": "step_index out of range"}
        modes = np.asarray(stored.modes[int(step_index)], dtype=int)
        expected = int(stored.executed_steps)
        if int(step_index) != expected:
            blocked = {
                "status": "blocked_out_of_sequence",
                "message": "plan steps must be executed in order",
                "plan_id": plan_id,
                "requested_step_index": int(step_index),
                "expected_step_index": expected,
                "executed_steps": list(stored.executed_indices),
            }
            self.trace.append("action/blocked_out_of_sequence", blocked)
            return blocked
        requested = {
            "plan_id": plan_id,
            "step_index": int(step_index),
            "modes": modes.astype(int).tolist(),
            "mode_names": [MODE_NAMES[m] for m in modes],
            "approved": bool(approved),
            "changes_plant_state": True,
        }
        self.trace.append("action/requested", requested)
        if not approved:
            return {
                "status": "approval_required",
                "message": "maintenance/derate/offline actions require explicit human approval",
                **requested,
            }
        if stored.verification is None or not bool(stored.verification.get("all_pass")):
            return {
                "status": "blocked",
                "message": "plan must pass independent high-fidelity verification before execution",
                **requested,
            }
        self.trace.append(
            "approval/granted",
            {"plan_id": plan_id, "step_index": int(step_index), "source": "explicit approved=true"},
        )
        effective_modes = safety_shield(self.plant, modes)
        shield_adjustment = int(np.sum(effective_modes != modes))
        _, profit, done, info = self.plant.step(effective_modes)
        stored.executed_steps += 1
        stored.executed_indices.append(int(step_index))
        ticket = "MNT-" + hashlib.sha256(f"{plan_id}:{step_index}".encode("utf-8")).hexdigest()[:8].upper()
        result = {
            "status": "executed",
            "ticket": ticket,
            "plan_id": plan_id,
            "step_index": int(step_index),
            "planned_modes": modes.astype(int).tolist(),
            "modes": effective_modes.astype(int).tolist(),
            "shield_adjustment": shield_adjustment,
            "profit": round(float(profit), 2),
            "production": round(float(info.production), 2),
            "failures": int(info.failures),
            "maintenances": int(info.maintenances),
            "done": bool(done),
            "hour": int(self.plant.state.hour if self.plant.state else 0),
        }
        self.trace.append("action/executed", result)
        return result

    def execute_verified_plan(self, plan_id: str, approved: bool = False, **_: Any) -> dict[str, Any]:
        """Execute every remaining step of a verified plan in strict order.

        This is a plan-level human approval action: AGH gates this destructive
        tool call, while the tool itself enforces the exact 0..horizon-1 order.
        """
        stored = self.plans.get(plan_id)
        if stored is None:
            return {"status": "error", "error": "unknown plan_id"}
        if stored.verification is None or not bool(stored.verification.get("all_pass")):
            return {"status": "blocked", "message": "plan must pass independent high-fidelity verification first"}
        remaining = [i for i in range(stored.horizon) if i not in stored.executed_indices]
        if not remaining:
            return {"status": "already_completed", "plan_id": plan_id, "executed_steps": list(stored.executed_indices)}
        if not approved:
            return {
                "status": "approval_required",
                "message": "the verified plan requires explicit human approval before execution",
                "plan_id": plan_id,
                "remaining_steps": remaining,
                "changes_plant_state": True,
            }
        results: list[dict[str, Any]] = []
        shield_adjustments = 0
        for step_index in remaining:
            modes = np.asarray(stored.modes[step_index], dtype=int)
            requested = {
                "plan_id": plan_id,
                "step_index": int(step_index),
                "modes": modes.astype(int).tolist(),
                "mode_names": [MODE_NAMES[m] for m in modes],
                "approved": True,
                "approval_scope": "verified-plan-level",
                "changes_plant_state": True,
            }
            self.trace.append("action/requested", requested)
            self.trace.append(
                "approval/granted",
                {"plan_id": plan_id, "step_index": int(step_index), "source": "verified plan approval"},
            )
            effective_modes = safety_shield(self.plant, modes)
            shield_adjustment = int(np.sum(effective_modes != modes))
            shield_adjustments += shield_adjustment
            _, profit, done, info = self.plant.step(effective_modes)
            stored.executed_steps += 1
            stored.executed_indices.append(int(step_index))
            ticket = "MNT-" + hashlib.sha256(f"{plan_id}:{step_index}".encode("utf-8")).hexdigest()[:8].upper()
            result = {
                "status": "executed",
                "ticket": ticket,
                "plan_id": plan_id,
                "step_index": int(step_index),
                "planned_modes": modes.astype(int).tolist(),
                "modes": effective_modes.astype(int).tolist(),
                "shield_adjustment": shield_adjustment,
                "profit": round(float(profit), 2),
                "production": round(float(info.production), 2),
                "failures": int(info.failures),
                "maintenances": int(info.maintenances),
                "done": bool(done),
                "hour": int(self.plant.state.hour if self.plant.state else 0),
            }
            self.trace.append("action/executed", result)
            results.append(result)
            if done:
                break
        actual_profit = float(sum(item["profit"] for item in results))
        actual_failures = int(sum(item["failures"] for item in results))
        verified_profit = float(stored.verification.get("verified_profit", 0.0))
        verified_failures = int(stored.verification.get("verified_failures", 0))
        self.calibration.n_runs += 1
        self.calibration.actual_profit_sum += actual_profit
        self.calibration.verified_profit_sum += verified_profit
        self.calibration.actual_failures += actual_failures
        self.calibration.verified_failures += verified_failures
        self.calibration.shield_adjustments += shield_adjustments
        actual_vs_verified = {
            "actual_profit": round(actual_profit, 2),
            "verified_profit": round(verified_profit, 2),
            "profit_ratio": round(actual_profit / verified_profit, 4) if verified_profit > 0 else None,
            "actual_failures": actual_failures,
            "verified_failures": verified_failures,
            "failure_delta": actual_failures - verified_failures,
            "shield_adjustments": shield_adjustments,
            "calibration": self.calibration.summary(),
        }
        self.trace.append("calibration/outcome", actual_vs_verified)
        return {
            "status": "executed_plan",
            "plan_id": plan_id,
            "executed_steps": list(stored.executed_indices),
            "results": results,
            "total_profit": round(actual_profit, 2),
            "total_failures": actual_failures,
            "final_hour": int(self.plant.state.hour if self.plant.state else 0),
            "done": bool(self.plant.state and self.plant.state.hour >= self.plant.episode_hours),
            "actual_vs_verified": actual_vs_verified,
        }

    def calibration_status(self, **_: Any) -> dict[str, Any]:
        return {"status": "ok", **self.calibration.summary()}

    def trace_export(self, **_: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "valid": self.trace.verify(),
            "n_events": len(self.trace.events),
            "last_hash": self.trace.last_hash,
            "events": self.trace.events,
        }

    # ------------------------------------------------------------------
    # Convenience for offline CLI/demo
    # ------------------------------------------------------------------
    def verified_plan(self, horizon: int | None = None) -> tuple[str, dict[str, Any], dict[str, Any]]:
        plan = self.world_model_plan(horizon=horizon)
        verification = self.highfidelity_verify(plan["plan_id"])
        return plan["plan_id"], plan, verification


TOOL_SPECS = [
    {
        "name": "plant_read_state",
        "description": "Read the current production and machine health state.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {
            "title": "Read plant state",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "world_model_plan",
        "description": "Generate a multi-step maintenance and production plan with the action-conditioned world model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "horizon": {"type": "integer", "minimum": 6, "maximum": 72, "default": 24},
                "risk_aware": {"type": "boolean", "default": True, "description": "Verify and rank Top-K candidates by CVaR/failure-risk score."},
            },
        },
        "annotations": {
            "title": "Plan with world model",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "highfidelity_verify",
        "description": "Verify a plan across independent high-fidelity digital-twin scenarios.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "n_scenarios": {"type": "integer", "minimum": 8, "maximum": 128, "default": 32},
            },
            "required": ["plan_id"],
        },
        "annotations": {
            "title": "Verify with digital twin",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "request_maintenance_action",
        "description": "Request or execute a plant-changing maintenance, derate or offline action after human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "step_index": {"type": "integer", "minimum": 0, "default": 0},
                "approved": {"type": "boolean", "default": False, "description": "Set true only after explicit human approval."},
            },
            "required": ["plan_id"],
        },
        "annotations": {
            "title": "Request maintenance action (approval required)",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "execute_verified_plan",
        "description": "Execute every remaining step of a verified maintenance plan in strict order after human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "approved": {"type": "boolean", "default": False, "description": "Set true only after explicit human approval of the verified plan."},
            },
            "required": ["plan_id"],
        },
        "annotations": {
            "title": "Execute verified plan (approval required)",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "plan_status",
        "description": "Read which plan steps have been executed and the next required step index.",
        "inputSchema": {
            "type": "object",
            "properties": {"plan_id": {"type": "string"}},
            "required": ["plan_id"],
        },
        "annotations": {
            "title": "Read plan status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "calibration_status",
        "description": "Read online calibration between actual execution and verified outcomes.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"title": "Read calibration status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "trace_export",
        "description": "Export the hash-chained AGH tool/action trace.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {
            "title": "Export trace",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
]


def call_tool(agent: MaintenanceAgent, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    mapping = {
        "plant_read_state": agent.plant_read_state,
        "world_model_plan": agent.world_model_plan,
        "highfidelity_verify": agent.highfidelity_verify,
        "request_maintenance_action": agent.request_maintenance_action,
        "execute_verified_plan": agent.execute_verified_plan,
        "plan_status": agent.plan_status,
        "calibration_status": agent.calibration_status,
        "trace_export": agent.trace_export,
    }
    if name not in mapping:
        return {"status": "error", "error": f"unknown tool: {name}"}
    return mapping[name](**arguments)
