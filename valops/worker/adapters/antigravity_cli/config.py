"""Generated Antigravity CLI configuration (HLD §6.5). Written by the controller before
launch; read-only at runtime.

Admission status: the endpoint override and key-less authentication are UNDOCUMENTED
(S13, [U]); headless mode reportedly ignores `permissions.allow` and can hang past
`--print-timeout` (S14). The expected outcome is NATIVE-ONLY [H]. The launcher refuses to
start unless W1-G has recorded a verified endpoint override in the configuration.
"""
from __future__ import annotations

import json


def settings_json() -> str:
    # NO permissions.allow entries. Allow-rules are not relied on in either direction (S14).
    return json.dumps({"permissions": {"allow": []}, "telemetry": {"enabled": False}, "autoUpdate": False}, indent=2)


def mcp_config_json(mcp_command: list[str]) -> str:
    # Path and schema reported by third parties only (C2) [U].
    return json.dumps({"mcpServers": {"valops": {"command": mcp_command[0], "args": mcp_command[1:]}}}, indent=2)
