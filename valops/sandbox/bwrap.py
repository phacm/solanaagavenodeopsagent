"""OS sandbox for workers (SR-11, D11 default: bubblewrap). Fails closed.

Profile (HLD §6.2, §6.5 common launcher):
  * all namespaces unshared, incl. network: the only interface is loopback, where the
    worker's bridge to the model broker listens;
  * root filesystem: a minimal read-only rootfs per runtime (``RootfsSpec.path``);
    ``host_ro`` binds a fixed list of host system dirs read-only and is for DEVELOPMENT
    ONLY -- it fails PC-2 inertness and carries no PA/G1 weight;
  * the fresh step home is bound read-only; no writable path unless the runtime needs a
    size-capped private tmpfs (discarded at step end);
  * broker sockets are bound individually (the worker's only IPC);
  * clearenv; die-with-parent; new session; no capabilities.

``available()`` probes the real backend; the controller refuses to spawn a worker if it
fails (RB-11). There is no unsandboxed fallback in this code base.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

HOST_RO_DIRS = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc/ssl", "/etc/ca-certificates", "/etc/alternatives",
                "/etc/ld.so.cache", "/etc/localtime")


class SandboxUnavailable(RuntimeError):
    pass


@dataclass
class RootfsSpec:
    path: str | None = None          # production: minimal per-runtime rootfs (worker-rootfs/<runtime>)
    host_ro: bool = False            # development only
    extra_ro: dict[str, str] = field(default_factory=dict)  # host path -> sandbox path (e.g. the valops package)


@dataclass
class SandboxSpec:
    rootfs: RootfsSpec
    home: str                        # host dir, generated per step, bound read-only at /home/valops
    bundle: str                      # host bundle dir, bound read-only at /bundle
    sockets: dict[str, str]          # host socket path -> sandbox path
    scratch_tmpfs_mb: int = 0        # 0 = no writable path at all
    env: dict[str, str] = field(default_factory=dict)


def bwrap_path() -> str | None:
    return shutil.which("bwrap")


def available() -> tuple[bool, str]:
    exe = bwrap_path()
    if not exe:
        return False, "bwrap not installed"
    try:
        r = subprocess.run([exe, "--unshare-all", "--die-with-parent", "--ro-bind", "/", "/", "true"],
                           capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"bwrap probe failed: {e}"
    if r.returncode != 0:
        return False, f"bwrap probe exit {r.returncode}: {r.stderr.decode(errors='replace')[:200]}"
    return True, "ok"


def build_argv(spec: SandboxSpec, command: list[str]) -> list[str]:
    exe = bwrap_path()
    if not exe:
        raise SandboxUnavailable("bwrap not installed")
    a = [exe, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv",
         "--hostname", "valops-worker"]
    if spec.rootfs.path:
        a += ["--ro-bind", spec.rootfs.path, "/"]
    elif spec.rootfs.host_ro:
        for d in HOST_RO_DIRS:
            a += ["--ro-bind-try", d, d]
    else:
        raise SandboxUnavailable("no rootfs configured")
    for host, inside in spec.rootfs.extra_ro.items():
        a += ["--ro-bind", host, inside]
    a += ["--proc", "/proc", "--dev", "/dev"]
    a += ["--ro-bind", spec.home, "/home/valops", "--ro-bind", spec.bundle, "/bundle"]
    a += ["--dir", "/run/valops"]
    for host, inside in spec.sockets.items():
        a += ["--bind", host, inside]  # a socket must be bound writable to connect(); it is not a file write path
    if spec.scratch_tmpfs_mb > 0:
        a += ["--size", str(spec.scratch_tmpfs_mb * 1024 * 1024), "--tmpfs", "/tmp"]
    env = {"HOME": "/home/valops", "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", **spec.env}
    for k, v in env.items():
        a += ["--setenv", k, v]
    a += ["--chdir", "/home/valops", "--"]
    return a + command
