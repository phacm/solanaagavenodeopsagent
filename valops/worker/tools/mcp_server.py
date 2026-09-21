"""Minimal MCP stdio server exposing ONLY the role's `valops` tools (PC-6), for the Codex and
Antigravity runtime adapters. JSON-RPC 2.0, newline-delimited, over stdin/stdout.

    python -m valops.worker.tools.mcp_server /home/valops/step.json
"""
from __future__ import annotations

import json
import sys

from .stubs import ToolStubs

PROTOCOL = "2025-06-18"


def serve(stubs: ToolStubs, inp=sys.stdin, out=sys.stdout) -> None:
    def send(obj: dict) -> None:
        out.write(json.dumps(obj) + "\n")
        out.flush()

    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
        if rid is None:  # notification (e.g. notifications/initialized)
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": params.get("protocolVersion", PROTOCOL),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "valops", "version": "0.5"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [
                {"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"]} for s in stubs.schemas()]}})
        elif method == "tools/call":
            name = params.get("name")
            if name not in stubs.allowed:
                res = {"error": "forbidden", "message": f"{name} is not available to this role"}
            else:
                res = stubs.call(name, params.get("arguments") or {})
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": ToolStubs.render(res)}], "isError": "error" in res}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"{method} not supported"}})


def main() -> None:
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    serve(ToolStubs(spec))


if __name__ == "__main__":
    main()
