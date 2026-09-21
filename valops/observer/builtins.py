"""Read-only builtins implemented in the daemon itself (no process spawn, or only a fixed
read-only argv). Bounded reads only: no full-log scans (OD-4)."""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from .parsers import running_version as parse_version


def _tail_bytes(path: str, max_bytes: int) -> bytes:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        return f.read(max_bytes)


def log_tail(args: dict, local: dict) -> tuple[str, dict]:
    lines = int(args["lines"])
    raw = _tail_bytes(local["logfile"], int(local.get("log_tail_max_bytes", 262144)))
    text = "\n".join(raw.decode(errors="replace").splitlines()[-lines:])
    return text, {"lines": min(lines, text.count("\n") + 1 if text else 0)}


def running_version(args: dict, local: dict) -> tuple[str, dict]:
    # Equivalent of `grep -B1 'Starting validator with' <logfile>` over a bounded tail.
    raw = _tail_bytes(local["logfile"], int(local.get("log_scan_max_bytes", 8 * 1024 * 1024))).decode(errors="replace")
    lines = raw.splitlines()
    hits = []
    for i, ln in enumerate(lines):
        if "Starting validator with" in ln:
            hits += lines[max(0, i - 1): i + 1]
    text = "\n".join(hits[-4:])
    return text, parse_version(text, local)


def _systemctl_is_active(unit: str) -> str:
    try:
        r = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=5, check=False)
        return r.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def host_metrics(args: dict, local: dict) -> tuple[str, dict]:
    vols = {}
    for name in ("ledger", "accounts"):
        path = local.get(f"{name}_path") or (local["ledger"] if name == "ledger" else None)
        if not path:
            continue
        try:
            du = shutil.disk_usage(path)
            vols[name] = {"free_pct": round(100.0 * du.free / du.total, 2), "free_gib": round(du.free / 2**30, 2)}
        except OSError as e:
            vols[name] = {"error": type(e).__name__}
    mem = {}
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            k, v = ln.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                mem[k] = int(v.split()[0])
    except OSError:
        pass
    state = _systemctl_is_active(local.get("unit_name", "sol.service"))
    frees = [v["free_pct"] for v in vols.values() if "free_pct" in v]
    structured = {
        "parsed": True, "volumes": vols, "min_free_pct": min(frees) if frees else None,
        "mem_available_pct": round(100.0 * mem["MemAvailable"] / mem["MemTotal"], 2) if len(mem) == 2 else None,
        "load1": os.getloadavg()[0], "unit_state": state, "unit_active": state == "active",
    }
    return json.dumps(structured), structured


def host_hygiene(args: dict, local: dict) -> tuple[str, dict]:
    pw_auth = "unknown"
    try:
        for ln in Path("/etc/ssh/sshd_config").read_text().splitlines():
            s = ln.strip()
            if s.lower().startswith("passwordauthentication"):
                pw_auth = s.split()[-1].lower()
    except OSError:
        pass
    ports: list[str] = []
    try:
        r = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True, timeout=5, check=False)
        ports = sorted({ln.split()[3].rsplit(":", 1)[-1] for ln in r.stdout.splitlines() if len(ln.split()) >= 4})[:100]
    except (OSError, subprocess.TimeoutExpired):
        pass
    pending = None
    stamp = Path("/var/lib/update-notifier/updates-available")
    if stamp.exists():
        try:
            pending = stamp.read_text()[:500]
        except OSError:
            pass
    structured = {"parsed": True, "ssh_password_authentication": pw_auth, "fail2ban_present": shutil.which("fail2ban-client") is not None,
                  "listening_tcp_ports": ports, "pending_updates_note": pending}
    return json.dumps(structured), structured


def consensus_state_files(args: dict, local: dict) -> tuple[str, dict]:
    ledger = local["ledger"]
    out: dict[str, Any] = {"parsed": True, "tower": [], "vote_history": []}
    for kind, pat in (("tower", "tower-*.bin"), ("vote_history", "vote_history-*.bin")):
        for p in sorted(glob.glob(os.path.join(ledger, pat)))[:10]:
            try:
                out[kind].append({"name": os.path.basename(p), "mtime": os.stat(p).st_mtime})
            except OSError:
                pass
    return json.dumps(out), out


def rpc_latency(args: dict, local: dict) -> tuple[str, dict]:
    url = local.get("rpc_url", "http://127.0.0.1:8899")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getHealth"}).encode()
    t0 = time.monotonic()
    ok, err = False, None
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=float(local.get("rpc_timeout_s", 5))) as r:
            ok = b'"ok"' in r.read(4096)
    except Exception as e:  # noqa: BLE001
        err = type(e).__name__
    ms = round((time.monotonic() - t0) * 1000, 1)
    structured = {"parsed": True, "latency_ms": ms, "healthy": ok, "error": err}
    return json.dumps(structured), structured


BUILTINS = {
    "log_tail": log_tail, "running_version": running_version, "host_metrics": host_metrics,
    "host_hygiene": host_hygiene, "consensus_state_files": consensus_state_files, "rpc_latency": rpc_latency,
}
