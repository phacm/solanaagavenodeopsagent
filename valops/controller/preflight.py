"""Controller pre-flight and degradation tiers (HLD §9, §9.1, NFR-5).

Full operation -> observe-only (bundle or chain integrity) -> sentinel-and-alert only
(no LLM step: model broker, audit path, anchor lag above P-19, sandbox backend) ->
watchtower only (ops host down). Every reason is reported; nothing degrades silently.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..common.canonical import now
from ..common.rpc import RpcClient, RpcError


@dataclass
class Preflight:
    observe_only: list[str] = field(default_factory=list)   # RB-3, RB-10
    no_llm: list[str] = field(default_factory=list)         # RB-8, RB-9, RB-11, RB-14 ...
    warnings: list[str] = field(default_factory=list)       # e.g. anchor lag above P-18

    @property
    def llm_allowed(self) -> bool:
        return not self.observe_only and not self.no_llm


class ObserveOnlyFlag:
    """Persisted so a restart does not silently leave observe-only. Cleared only by an
    operator after the runbook exit condition holds (RB-3, RB-10)."""

    def __init__(self, path: Path):
        self.path = path

    def set(self, reason: str) -> None:
        if not self.path.exists():
            self.path.write_text(json.dumps({"reason": reason, "ts": now()}))

    def get(self) -> str | None:
        try:
            return json.loads(self.path.read_text())["reason"]
        except (FileNotFoundError, ValueError, KeyError):
            return None

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def run(*, flag: ObserveOnlyFlag, bundles, audit_status, brokers: dict[str, RpcClient], launcher,
        anchor_interval_s: float, max_anchor_lag_s: float) -> Preflight:
    pf = Preflight()
    reason = flag.get()
    if reason:
        pf.observe_only.append(f"observe-only: {reason}")
    active = bundles.active()
    if not active:
        pf.observe_only.append("no active bundle")
    else:
        r = bundles.verify(active)
        if r:
            pf.observe_only.append(f"active bundle fails verification: {r}")
    try:
        st = audit_status()
        if st.get("integrity_error"):
            pf.observe_only.append(f"audit chain: {st['integrity_error']}")
        lag = st.get("anchor_lag_s")
        if lag is None or lag > max_anchor_lag_s:
            pf.no_llm.append(f"anchor lag {lag if lag is None else int(lag)}s above P-19 ({int(max_anchor_lag_s)}s)")
        elif lag > anchor_interval_s * 1.5:
            pf.warnings.append(f"anchor lag {int(lag)}s above P-18")
    except RpcError as e:
        pf.no_llm.append(f"audit sequencer unavailable: {e.code}")
    for name, client in brokers.items():
        try:
            client.call("ping")
        except RpcError as e:
            pf.no_llm.append(f"{name} unavailable: {e.code}")
    why = launcher.preflight()
    if why:
        pf.no_llm.append(f"sandbox backend unavailable: {why}")
    return pf
