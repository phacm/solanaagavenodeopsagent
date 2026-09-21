"""`codex exec` launcher (HLD §6.5, W21). Only used if W1-O admits the runtime (D20).

CODEX_HOME was generated read-only by the controller (config.toml + AGENTS.md from the
bundle). The only model route is the in-sandbox bridge to the model broker; the only tool
source is the `valops` MCP stub server. PC-2 inertness of Codex's built-in shell is an
admission test, not an assumption. Output is kept on stderr (transcript; never parsed by
the control plane)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from ...tools.stubs import user_message


def run(spec: dict, timeout_s: float) -> None:
    exe = shutil.which("codex")
    if not exe:
        raise RuntimeError("codex binary not present in this rootfs")
    env = {
        "HOME": "/home/valops", "CODEX_HOME": "/home/valops/.codex", "PATH": os.environ.get("PATH", "/usr/bin"),
        "VALOPS_PLACEHOLDER_KEY": "placeholder-not-a-secret", "LANG": "C.UTF-8",
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }
    argv = [exe, "exec", "--skip-git-repo-check", "--json", "-C", "/home/valops", user_message(spec)]  # flags [U] W1-O
    subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr,
                   timeout=timeout_s, check=False)
