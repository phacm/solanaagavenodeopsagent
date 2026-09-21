"""`PreToolUse` policy gate -- DEFENCE IN DEPTH ONLY (HLD §6.3, SR-4, W10).

Runs inside the untrusted worker, so it is NOT a trust boundary and no security property
depends on it. It exists to fail fast, give the model a legible denial reason, and leave a
first-line audit record. Every check is repeated by the broker that serves the call.

Checks, in order: 1 allowlist · 2 schema · 3 local rate · 4 legal in state · 5 bundle verifies.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ...common.schema import SchemaError, validate
from ...common.tools import TOOLS_BY_NAME

MCP_PREFIX = "mcp__valops__"


def _bundle_ok(bundle_path: str) -> bool:
    """Recompute the manifest over the read-only bundle mount (cheap local re-check)."""
    root = Path(bundle_path)
    try:
        recorded = (root / "MANIFEST.sha256").read_text().splitlines()
    except OSError:
        return False
    for line in recorded:
        if not line.strip():
            continue
        h, rel = line.split("  ", 1)
        try:
            if hashlib.sha256((root / rel).read_bytes()).hexdigest() != h:
                return False
        except OSError:
            return False
    return True


class PolicyGate:
    def __init__(self, spec: dict):
        self.role = spec["role"]
        self.allowed = set(spec["tools"])
        self.state = spec["state"]
        self.tool_states = spec["tool_states"]
        self.max_calls = int(spec["max_turns"]) * 3
        self.bundle_path = spec["bundle_path"]
        self.calls = 0

    def check(self, tool_name: str, args: Any) -> str | None:
        name = tool_name[len(MCP_PREFIX):] if tool_name.startswith(MCP_PREFIX) else tool_name
        if name not in self.allowed:
            return f"{tool_name} is not in the {self.role} allowlist"
        try:
            validate(args or {}, TOOLS_BY_NAME[name].input_schema)
        except SchemaError as e:
            return f"arguments invalid: {e}"
        self.calls += 1
        if self.calls > self.max_calls:
            return "per-session tool-call quota exhausted"
        if self.state not in self.tool_states.get(name, []):
            return f"{name} is not legal in episode state {self.state}"
        if not _bundle_ok(self.bundle_path):
            return "bound bundle failed verification"
        return None

    async def hook(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        reason = self.check(input_data.get("tool_name", ""), input_data.get("tool_input"))
        if reason is None:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
