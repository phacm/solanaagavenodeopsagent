"""Sentinel rules [1] (HLD §5.1, §5.9): pure functions over samples -> findings.
No model involvement. Thresholds come from the bound bundle (parameter register)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Finding:
    cls: str            # validator_health | telemetry_health
    check: str
    severity: str       # info | warning | high | critical
    detail: str
    command_ids: tuple[str, ...] = field(default_factory=tuple)


def _ok(s: dict | None) -> dict | None:
    """Structured output of a successful, parsed sample; otherwise None (missing data)."""
    if not s or s.get("status") != "ok":
        return None
    st = s.get("structured") or {}
    return st if st.get("parsed") else None


class ConsecutiveCounter:
    def __init__(self) -> None:
        self.n: dict[str, int] = {}

    def update(self, key: str, breached: bool) -> int:
        self.n[key] = self.n.get(key, 0) + 1 if breached else 0
        return self.n[key]


def validator_findings(samples: dict[str, dict], bundle, counter: ConsecutiveCounter) -> list[Finding]:
    """TH-2: missing data NEVER opens, escalates, de-escalates or resolves a validator-health
    episode. Every rule below fires only on a successful, parsed sample."""
    out: list[Finding] = []
    p = bundle.thresholds
    hm = _ok(samples.get("host_metrics"))
    if hm is not None:
        if hm.get("unit_active") is False:
            out.append(Finding("validator_health", "unit_state", "high", f"unit state {hm.get('unit_state')}", ("host_metrics",)))
        mf = hm.get("min_free_pct")
        if isinstance(mf, (int, float)) and mf < p["P-04"]:
            out.append(Finding("validator_health", "disk_headroom", "high", f"min free {mf}% < {p['P-04']}%", ("host_metrics",)))
    cu = _ok(samples.get("catchup"))
    if cu is not None:
        n = counter.update("delinquency", cu["slots_behind"] > p["P-03"]["threshold"])
        if n >= p["P-03"]["samples"]:
            out.append(Finding("validator_health", "delinquency", "high",
                               f"{cu['slots_behind']} slots behind for {n} samples", ("catchup", "validator_monitor", "host_metrics")))
    bal = _ok(samples.get("identity_balance"))
    if bal is not None and bal["balance_sol"] < p["P-02"]:
        sev = "high" if bal["balance_sol"] < p["P-02"] / 2 else "warning"
        out.append(Finding("validator_health", "balance", sev, f"{bal['balance_sol']} SOL < floor {p['P-02']}", ("identity_balance",)))
    rv = _ok(samples.get("running_version"))
    exp = bundle.deployment["expected_version"]
    if rv is not None and rv.get("version") and rv["version"] != exp:
        out.append(Finding("validator_health", "version_drift", "warning", f"running {rv['version']} != expected {exp}",
                           ("running_version",)))
    return out


def telemetry_findings(telemetry: dict, probe: dict, bundle, watchtower_age_s: float | None) -> list[Finding]:
    """TH-1: breaching an owner-set threshold opens a telemetry_health episode."""
    out: list[Finding] = []
    p = bundle.thresholds
    stale_after = p["P-15"] * p["P-01"]
    tcfg = bundle.deployment.get("telemetry") or {}
    if not probe.get("reachable", False) or telemetry.get("consecutive_unreachable", 0) >= 2:
        out.append(Finding("telemetry_health", "observer_unreachable", "high",
                           str(probe.get("error") or telemetry.get("last_unreachable_error"))[:200]))
        return out  # everything else is a consequence
    lat = probe.get("latency_ms")
    if isinstance(lat, (int, float)) and lat > float(tcfg.get("observer_latency_ms_max", 5000)):
        out.append(Finding("telemetry_health", "observer_slow", "warning", f"probe latency {lat} ms"))
    for cid, s in (telemetry.get("per_command") or {}).items():
        if cid == "health":
            continue
        if s.get("age_s") is not None and s["age_s"] > stale_after:
            out.append(Finding("telemetry_health", "sample_stale", "high", f"{cid} newest sample {s['age_s']}s old"))
            break
    for cid, s in (telemetry.get("per_command") or {}).items():
        if (s.get("error_rate") or 0) > float(tcfg.get("error_rate_max", 0.5)):
            out.append(Finding("telemetry_health", "command_errors", "warning", f"{cid} error rate {s['error_rate']}"))
            break
    br = telemetry.get("breaker") or probe.get("breaker") or {}
    if br.get("open"):
        # TH-4: the system does not go quiet to protect itself without saying so.
        out.append(Finding("telemetry_health", "rpc_breaker_open", "warning", f"local-RPC breaker open (trips {br.get('trips')})"))
    if watchtower_age_s is not None and watchtower_age_s > stale_after:
        out.append(Finding("telemetry_health", "watchtower_silent", "warning", f"no watchtower heartbeat for {int(watchtower_age_s)}s"))
    return out


def stale_checks(telemetry: dict, bundle) -> list[str]:
    stale_after = bundle.thresholds["P-15"] * bundle.thresholds["P-01"]
    return sorted(cid for cid, s in (telemetry.get("per_command") or {}).items()
                  if cid != "health" and (s.get("age_s") is None or s["age_s"] > stale_after))


def summarise(sample: dict[str, Any]) -> dict[str, Any]:
    return {k: sample.get(k) for k in ("command_id", "status", "structured", "truncated", "collected_at", "flags", "audit_ref")}
