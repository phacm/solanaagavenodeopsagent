"""`agy -p` launcher (HLD §6.5, W22). Only used if W1-G admits the runtime (D20).

Refuses to run unless the configuration records a W1-G-verified endpoint override
(`endpoint_override_env`), because headless auth otherwise uses a cached interactive
login, which PC-4 prohibits in the worker. `--dangerously-skip-permissions` is never
passed. Expected outcome is native-only [H]."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from ...tools.stubs import user_message


class NotAdmitted(RuntimeError):
    pass


def run(spec: dict, timeout_s: float) -> None:
    conf = spec["configuration"]
    override = conf.get("endpoint_override_env")
    if not override or conf.get("admission") != "admitted":
        raise NotAdmitted("Antigravity runtime has no verified broker endpoint override (PC-4); use the native adapter")
    exe = shutil.which("agy")
    if not exe:
        raise RuntimeError("agy binary not present in this rootfs")
    env = {"HOME": "/home/valops", "PATH": os.environ.get("PATH", "/usr/bin"), "LANG": "C.UTF-8",
           override: f"http://127.0.0.1:{spec['model_port']}/google", "PYTHONPATH": os.environ.get("PYTHONPATH", "")}
    argv = [exe, "-p", user_message(spec), "--output-format", "stream-json", "--model", conf["model"],
            "--print-timeout", str(max(30, int(timeout_s) - 30))]  # below P-11; the controller kills at P-11 anyway
    subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr,
                   timeout=timeout_s, check=False)
