"""Run one fresh Claude Agent SDK session for one role and one episode (R-1)."""
from __future__ import annotations

import asyncio
import sys

from ....common.artefact_schema import ARTEFACT_SCHEMA
from ...tools.stubs import ToolStubs, user_message
from .options import build_options


async def _run(spec: dict, stubs: ToolStubs, prompt_path: str) -> dict | None:
    from claude_agent_sdk import ResultMessage, query

    options = build_options(spec, stubs, prompt_path, ARTEFACT_SCHEMA[spec["role"]])
    structured = None
    async for msg in query(prompt=user_message(spec), options=options):
        if isinstance(msg, ResultMessage):
            structured = getattr(msg, "structured_output", None)
            print(f"claude_sdk: turns={msg.num_turns} cost={msg.total_cost_usd} "
                  f"denials={len(msg.permission_denials or [])}", file=sys.stderr)
    return structured if isinstance(structured, dict) else None


def run(spec: dict, stubs: ToolStubs, prompt_path: str) -> dict | None:
    return asyncio.run(_run(spec, stubs, prompt_path))
