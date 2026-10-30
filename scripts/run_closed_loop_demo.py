"""Run the full MCP maintenance loop and persist auditable artifacts.

This is a deterministic contract demonstration. For the competition, run
`agnes/AGH_RUNBOOK.md` inside a real AGH session and export the AGH Trace.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)


def rpc(proc: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    assert proc.stdin is not None and proc.stdout is not None
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server terminated")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError(response["error"])
    return response["result"]


def tool(proc: subprocess.Popen[str], request_id: int, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    result = rpc(proc, request_id, "tools/call", {"name": name, "arguments": args or {}})
    return result["structuredContent"]


def main() -> int:
    import os
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "wm_maint.mcp_server"],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    events: list[dict[str, Any]] = []
    try:
        rpc(proc, 1, "initialize")
        events.append({"step": "initialize", "result": "ready"})
        state = tool(proc, 2, "plant_read_state")
        events.append({"step": "plant_read_state", "result": state})
        plan = tool(proc, 3, "world_model_plan", {"horizon": 12})
        events.append({"step": "world_model_plan", "result": plan})
        verification = tool(proc, 4, "highfidelity_verify", {"plan_id": plan["plan_id"]})
        events.append({"step": "highfidelity_verify", "result": verification})
        request = tool(proc, 5, "request_maintenance_action", {"plan_id": plan["plan_id"], "step_index": 0, "approved": False})
        events.append({"step": "approval_requested", "result": request})
        executed = tool(proc, 6, "request_maintenance_action", {"plan_id": plan["plan_id"], "step_index": 0, "approved": True})
        events.append({"step": "action_executed", "result": executed})
        trace = tool(proc, 7, "trace_export")
        events.append({"step": "trace_export", "result": trace})
        report = {
            "schema": "wm-maintenance-agent/1.0",
            "trace_valid": trace["valid"],
            "n_trace_events": trace["n_events"],
            "plan_id": plan["plan_id"],
            "verified_profit": verification["verified_profit"],
            "ticket": executed["ticket"],
            "events": events,
        }
        (OUT / "closed_loop_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        trace_path = OUT / "mcp_trace.jsonl"
        with trace_path.open("w", encoding="utf-8") as fh:
            for event in trace["events"]:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        print("closed-loop report written:", OUT / "closed_loop_report.json")
        print(json.dumps({"trace_valid": trace["valid"], "trace_events": trace["n_events"], "ticket": executed["ticket"], "verified_profit": verification["verified_profit"]}, ensure_ascii=False, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
