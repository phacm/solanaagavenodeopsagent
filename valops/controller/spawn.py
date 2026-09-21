"""Worker spawn (HLD §4.1 "fork/exec per step", §6.5 common launcher, R-1, R-10, PC-1, PC-3).

The controller writes a FRESH home directory per step (step spec, bundle-generated
runtime configuration), then launches exactly one worker inside the sandbox under the
worker uid. The process tree is killed at P-11 whatever the runtime's own timeout.
The worker's stdout is read for ONE thing: a final JSON line carrying structured output
for the §5.8 cross-check. stderr (transcript/log text) is captured, capped, and handed
to the audit sequencer by reference -- it is parsed by nothing (R-9).
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..sandbox.bwrap import RootfsSpec, SandboxSpec, SandboxUnavailable, available, build_argv
from ..worker.adapters.antigravity_cli import config as agy_cfg
from ..worker.adapters.codex_cli import config as codex_cfg

MODEL_PORT = 18080
WORKER_PY = "/usr/bin/python3"
MCP_COMMAND = [WORKER_PY, "-m", "valops.worker.tools.mcp_server", "/home/valops/step.json"]
SOCKETS_INSIDE = {"episode": "/run/valops/episode.sock", "observer": "/run/valops/observer.sock",
                  "report": "/run/valops/report.sock", "model": "/run/valops/model.sock"}
STDERR_CAP = 1024 * 1024


@dataclass
class LaunchResult:
    exit_code: int | None
    timed_out: bool
    structured_output: dict | None
    stderr: bytes


def build_home(steps_dir: Path, session_id: str, spec: dict, prompt_text: str, adapter: str) -> Path:
    home = steps_dir / session_id
    home.mkdir(parents=True, exist_ok=False)
    (home / "step.json").write_text(json.dumps(spec))
    if adapter == "codex_cli":
        d = home / ".codex"
        d.mkdir()
        (d / "config.toml").write_text(codex_cfg.config_toml(model=spec["configuration"]["model"], port=MODEL_PORT,
                                                              mcp_command=MCP_COMMAND))
        (home / "AGENTS.md").write_text(codex_cfg.agents_md(prompt_text))
    elif adapter == "antigravity_cli":
        d = home / ".gemini" / "antigravity-cli"
        d.mkdir(parents=True)
        (d / "settings.json").write_text(agy_cfg.settings_json())
        (d / "mcp_config.json").write_text(agy_cfg.mcp_config_json(MCP_COMMAND))
    for p in sorted(home.rglob("*"), reverse=True):
        os.chmod(p, 0o550 if p.is_dir() else 0o440)
    os.chmod(home, 0o550)
    return home


def remove_home(home: Path) -> None:
    for p in home.rglob("*"):
        os.chmod(p, 0o700)
    os.chmod(home, 0o700)
    shutil.rmtree(home, ignore_errors=True)


class BwrapLauncher:
    def __init__(self, rootfs: dict[str, RootfsSpec], *, worker_uid: int | None = None, worker_gid: int | None = None,
                 scratch_mb: dict[str, int] | None = None, python_path: str = "/opt/valops"):
        self.rootfs = rootfs
        self.worker_uid, self.worker_gid = worker_uid, worker_gid
        self.scratch_mb = scratch_mb or {}
        self.python_path = python_path

    def preflight(self) -> str | None:
        ok, why = available()
        return None if ok else why

    def run(self, *, adapter: str, home: Path, bundle_dir: Path, sockets: dict[str, str], timeout_s: float) -> LaunchResult:
        ok, why = available()
        if not ok:
            raise SandboxUnavailable(why)  # RB-11: never run a worker unsandboxed
        rootfs = self.rootfs.get(adapter)
        if rootfs is None:
            raise SandboxUnavailable(f"no rootfs configured for adapter {adapter}")
        spec = SandboxSpec(rootfs=rootfs, home=str(home), bundle=str(bundle_dir),
                           sockets={host: SOCKETS_INSIDE[k] for k, host in sockets.items()},
                           scratch_tmpfs_mb=self.scratch_mb.get(adapter, 0),
                           env={"PYTHONPATH": self.python_path, "PYTHONDONTWRITEBYTECODE": "1",
                                "VALOPS_PLACEHOLDER_KEY": "placeholder-not-a-secret"})
        argv = build_argv(spec, [WORKER_PY, "-m", "valops.worker.main", "/home/valops/step.json"])
        kwargs = {}
        if self.worker_uid is not None:
            kwargs.update(user=self.worker_uid, group=self.worker_gid, extra_groups=[])
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, close_fds=True, **kwargs)
        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # PC-1: kill the whole tree at P-11
            except ProcessLookupError:
                pass
            out, err = proc.communicate()
        return LaunchResult(proc.returncode, timed_out, _last_json_line(out), err[:STDERR_CAP])


def _last_json_line(out: bytes) -> dict | None:
    for line in reversed(out.decode(errors="replace").strip().splitlines()[-3:]):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        so = obj.get("structured_output") if isinstance(obj, dict) else None
        return so if isinstance(so, dict) else None
    return None
