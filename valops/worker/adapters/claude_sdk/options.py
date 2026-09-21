"""Reference adapter: per-role ClaudeAgentOptions factory (HLD §6.1, plan §5.2).

Every field is a W1 verification item on the D1/D7-pinned `claude-agent-sdk`. Where W1
shows the SDK behaves differently, §6 is amended and this factory follows it.
"""
from __future__ import annotations

from typing import Any

from ...hooks.audit import AuditHooks
from ...hooks.policy_gate import MCP_PREFIX, PolicyGate
from ...tools.stubs import ToolStubs

DISALLOWED = ["Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Task"]

# SDK sandbox intent (§6.2). The SDK sandbox is the third of four layers and never the
# control; `failIfUnavailable` was absent in 0.2.154 (X1), so fail-closed is obtained
# OUTSIDE the SDK: the controller refuses to spawn when bwrap is unavailable (RB-11).
SANDBOX_PROFILE: dict[str, Any] = {
    "enabled": True,
    "autoAllowBashIfSandboxed": False,
    "allowUnsandboxedCommands": False,
    "excludedCommands": [],
    "enableWeakerNestedSandbox": False,
    "network": {"allowedDomains": [], "allowUnixSockets": ["/run/valops/model.sock"], "allowLocalBinding": False},
}


def valops_stub_server(stubs: ToolStubs):
    from claude_agent_sdk import create_sdk_mcp_server, tool

    def make(name: str, description: str, schema: dict):
        @tool(name, description, schema)
        async def _t(args: dict) -> dict:
            res = stubs.call(name, args)
            return {"content": [{"type": "text", "text": ToolStubs.render(res)}], "is_error": "error" in res}
        return _t

    return create_sdk_mcp_server(name="valops", version="0.5",
                                 tools=[make(s["name"], s["description"], s["input_schema"]) for s in stubs.schemas()])


def build_options(spec: dict, stubs: ToolStubs, system_prompt_path: str, output_schema: dict):
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

    names = [MCP_PREFIX + t for t in spec["tools"]]
    gate, audit = PolicyGate(spec), AuditHooks(stubs)
    return ClaudeAgentOptions(
        setting_sources=[],                                   # no filesystem settings discovery
        tools=["Skill", *names] if not spec["inlined_prompts"] else names,
        allowed_tools=names,                                  # exact names, no globs
        disallowed_tools=DISALLOWED,                          # removed from context; Task forbids subagents
        mcp_servers={"valops": valops_stub_server(stubs)},
        strict_mcp_config=True,
        permission_mode="dontAsk",                            # unapproved => denied; canUseTool never called
        hooks={                                               # DEFENCE IN DEPTH ONLY (§6.3)
            "PreToolUse": [HookMatcher(hooks=[gate.hook]), HookMatcher(hooks=[audit.pre])],
            "PostToolUse": [HookMatcher(hooks=[audit.post])],
            "PostToolUseFailure": [HookMatcher(hooks=[audit.failure])],
        },
        sandbox=SANDBOX_PROFILE,
        system_prompt={"type": "file", "path": system_prompt_path},
        output_format={"type": "json_schema", "schema": output_schema},  # cross-check only (§5.8)
        max_turns=int(spec["max_turns"]),                     # P-05
        max_budget_usd=float(spec["max_budget_usd"]),         # P-06 (the broker enforces it again)
        model=spec["configuration"]["model"],                 # pinned (D7)
        continue_conversation=False, resume=None, fork_session=False,   # R-1
        agents=None, plugins=[],
        env={                                                 # no provider credential (§4.3)
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{spec['model_port']}/anthropic",
            "ANTHROPIC_API_KEY": "placeholder-not-a-secret",
            "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    )
