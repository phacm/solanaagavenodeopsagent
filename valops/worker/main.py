"""Worker [7] entry point: ONE adapter, ONE role, ONE episode (HLD §4.1, §6.5).

    python -m valops.worker.main /home/valops/step.json

Untrusted. Runs inside the OS sandbox with no provider credential, no writable path and no
network but the loopback bridge to its model-broker socket. stdout carries exactly one
final JSON line {"structured_output": ...} for the controller's cross-check; everything
else goes to stderr.
"""
from __future__ import annotations

import json
import sys

from . import bridge
from .tools.stubs import ToolStubs


def main() -> int:
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    stdout, sys.stdout = sys.stdout, sys.stderr  # nothing but the final line reaches real stdout
    bridge.start(int(spec["model_port"]), spec["sockets"]["model"])
    stubs = ToolStubs(spec)
    conf = spec["configuration"]
    prompt_path = f"{spec['bundle_path']}/prompts/{spec['role']}{'.inlined' if spec['inlined_prompts'] else ''}.md"
    structured = None
    adapter = conf["adapter"]
    if adapter == "claude_sdk":
        from .adapters.claude_sdk.run import run as run_claude
        structured = run_claude(spec, stubs, prompt_path)
    elif adapter == "native":
        from .adapters.native.loop import binding_for, run as run_native
        with open(prompt_path) as f:
            run_native(binding_for(conf["provider"], spec), spec, f.read(), stubs)
    elif adapter == "codex_cli":
        from .adapters.codex_cli.launcher import run as run_codex
        run_codex(spec, timeout_s=float(spec.get("timeout_s", 280)))
    elif adapter == "antigravity_cli":
        from .adapters.antigravity_cli.launcher import run as run_agy
        run_agy(spec, timeout_s=float(spec.get("timeout_s", 280)))
    else:
        print(f"unknown adapter {adapter}", file=sys.stderr)
        return 2
    stdout.write(json.dumps({"structured_output": structured}) + "\n")
    stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
