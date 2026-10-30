"""Zero-dependency MCP stdio server for the maintenance agent.

Implements the small JSON-RPC surface required by AGH:
initialize, ping, tools/list, tools/call and notification handling.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .config import PROJECT_ROOT
from .tools import MaintenanceAgent, TOOL_SPECS, call_tool


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "wm-maintenance-agent"


class MCPServer:
    def __init__(self, model_path: str | None = None) -> None:
        self.agent = MaintenanceAgent(model_path=model_path)
        self.initialized = False

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}
        if request_id is None:
            # Notifications do not receive a response.
            return None
        try:
            if method == "initialize":
                self.initialized = True
                return self._result(request_id, {
                    "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
                })
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                return self._result(request_id, {"tools": TOOL_SPECS})
            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if not isinstance(name, str):
                    raise ValueError("tools/call requires a string name")
                if not isinstance(arguments, dict):
                    raise ValueError("tools/call arguments must be an object")
                result = call_tool(self.agent, name, arguments)
                is_error = str(result.get("status", "")).lower() == "error"
                return self._result(request_id, {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                    "structuredContent": result,
                    "isError": is_error,
                })
            return self._error(request_id, -32601, f"method not found: {method}")
        except Exception as exc:  # Keep the server alive and return a structured error.
            return self._error(request_id, -32603, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _result(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(model_path: str | None = None) -> int:
    server = MCPServer(model_path=model_path)
    debug_path = PROJECT_ROOT / "artifacts" / "mcp_debug.jsonl" if os.environ.get("WM_MCP_DEBUG") else None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            response = server.handle(message)
        if response is not None:
            wire = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
            if debug_path is not None:
                try:
                    with debug_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"request": message, "response": response}, ensure_ascii=False) + "\n")
                except Exception:
                    pass
            sys.stdout.write(wire + "\n")
            sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MCP stdio server for the world-model maintenance agent")
    parser.add_argument("--model", default=str(PROJECT_ROOT / "artifacts" / "world_model.npz"))
    args = parser.parse_args(argv)
    return serve(args.model)


if __name__ == "__main__":
    raise SystemExit(main())
