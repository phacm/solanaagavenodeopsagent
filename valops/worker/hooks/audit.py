"""Audit hooks (defence in depth). They submit a first-line record through the episode
broker, which stamps role/session from the verified token; the sequencer stamps the actor.
The authoritative transcript is the model broker's (HLD §5.12 step 9)."""
from __future__ import annotations

from typing import Any


class AuditHooks:
    def __init__(self, stubs):
        self.stubs = stubs

    async def pre(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.stubs.audit_note("PreToolUse", {"tool": input_data.get("tool_name"), "tool_use_id": tool_use_id})
        return {}

    async def post(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.stubs.audit_note("PostToolUse", {"tool": input_data.get("tool_name"), "tool_use_id": tool_use_id})
        return {}

    async def failure(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.stubs.audit_note("PostToolUseFailure", {"tool": input_data.get("tool_name"), "tool_use_id": tool_use_id,
                                                     "error": str(input_data.get("error", ""))[:300]})
        return {}
