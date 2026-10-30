"""End-to-end MCP smoke test.

This is not a substitute for a real AGH session; it verifies the wire contract
that AGH will call. The accompanying AGH_RUNBOOK.md is used to capture the real
AGH Trace.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def request(proc: subprocess.Popen[str], message: dict) -> dict:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server closed stdout")
    return json.loads(line)


def call(proc: subprocess.Popen[str], request_id: int, name: str, arguments: dict | None = None) -> dict:
    response = request(proc, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    })
    if "error" in response:
        raise RuntimeError(response["error"])
    return response["result"]["structuredContent"]


def main() -> int:
    command = [PYTHON, "-m", "wm_maint.mcp_server"]
    env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        command,
        cwd=str(ROOT),
        env={**__import__("os").environ, **env},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        init = request(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        tools = request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert init["result"]["serverInfo"]["name"] == "wm-maintenance-agent"
        names = [t["name"] for t in tools["result"]["tools"]]
        assert names == ["plant_read_state", "world_model_plan", "highfidelity_verify", "request_maintenance_action", "execute_verified_plan", "plan_status", "calibration_status", "trace_export"]
        state = call(proc, 3, "plant_read_state")
        assert state["status"] == "ok"
        plan = call(proc, 4, "world_model_plan", {"horizon": 12})
        assert plan["status"] == "ok"
        verified = call(proc, 5, "highfidelity_verify", {"plan_id": plan["plan_id"]})
        assert verified["all_pass"] is True, verified
        status = call(proc, 6, "plan_status", {"plan_id": plan["plan_id"]})
        assert status["next_step_index"] == 0, status
        blocked = call(proc, 7, "request_maintenance_action", {"plan_id": plan["plan_id"], "step_index": 0, "approved": False})
        assert blocked["status"] == "approval_required", blocked
        executed = call(proc, 8, "request_maintenance_action", {"plan_id": plan["plan_id"], "step_index": 0, "approved": True})
        assert executed["status"] == "executed", executed
        status = call(proc, 9, "plan_status", {"plan_id": plan["plan_id"]})
        assert status["next_step_index"] == 1, status
        trace = call(proc, 10, "trace_export")
        assert trace["valid"] is True and trace["n_events"] >= 5
        print("MCP RESULT: ALL PASS")
        print(json.dumps({"tools": names, "verified_profit": verified["verified_profit"], "ticket": executed["ticket"], "trace_events": trace["n_events"]}, ensure_ascii=False, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
