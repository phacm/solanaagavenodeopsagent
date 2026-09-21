# Minimal per-runtime worker root filesystems (HLD §6.5, PC-2, W6)

One read-only rootfs per adapter, bound as `/` inside bubblewrap:

| Adapter | Contents |
|---|---|
| `native` | python3 + `valops` package + pinned `anthropic` / `openai` / `google-genai` clients and their libs. No shell, no coreutils. |
| `claude_sdk` | as `native` + pinned `claude-agent-sdk` and the CLI it drives (node runtime). |
| `codex_cli` | pinned `codex` binary + python3 + `valops` (for the MCP stub server). |
| `antigravity_cli` | pinned `agy` binary + python3 + `valops`. Expected native-only [H]. |

`/usr/bin/python3` and `/opt/valops` (PYTHONPATH) are the paths the controller assumes.
Build with a reproducible tool (e.g. `debootstrap --variant=minbase` then prune, or a
distroless image export) pinned under D7; record the rootfs hash with the PA record. The
development stack binds host system dirs read-only instead (`host_ro_dev`) — that fails
PC-2 inertness and has no gate weight.
