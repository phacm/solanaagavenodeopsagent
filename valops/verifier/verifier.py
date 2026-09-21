"""Verifier [6] -- recovery confirmation (HLD §5.6, §7.3, DD-4, DD-11, TH-3, W15).

Deterministic. For every non-terminal episode, re-sample the rule's commands through the
observer broker, evaluate the bound bundle's declarative predicate, and:

  * state `awaiting_operator` and predicate held for W consecutive FRESH samples
      -> append verification(pass), CAS set_state(resolved)   [store-verify endpoint]
  * predicate holds in any earlier state -> append ONE recovery_observation per streak and
      change nothing (a step in flight is never cancelled)
  * `handed_off` and predicate holds -> recovery_observation only; never reopened
  * stale or missing samples never confirm recovery (TH-3); past the P-17 deadline the
      episode stays `awaiting_operator` and the alert escalates -- the verifier never hands off
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from ..bundle.registry import BundleRegistry
from ..common.canonical import now
from ..common.rpc import RpcClient, RpcError
from .rules import evaluate, window

log = logging.getLogger(__name__)


class Verifier:
    def __init__(self, store_verify: RpcClient, observer_system: RpcClient, report_system: RpcClient, bundles: BundleRegistry,
                 audit=None):
        self.store = store_verify
        self.observer = observer_system
        self.report = report_system
        self.bundles = bundles
        self.audit = audit
        self.streak: dict[tuple[str, str], int] = {}
        self.escalated: set[str] = set()
        self.recovered_after_handoff: set[str] = set()

    def _sample(self, cids: list[str], max_age_s: float, bundle=None) -> tuple[dict, bool]:
        out: dict[str, Any] = {}
        fresh = True
        for cid in cids:
            if cid == "telemetry":
                try:
                    probe = self.observer.call("probe")
                    tel = self.observer.call("telemetry")
                    out["telemetry"] = {**tel, "probe_reachable": bool(probe.get("reachable")),
                                        "probe_latency_ms": probe.get("latency_ms"),
                                        "breaker_open": bool((tel.get("breaker") or probe.get("breaker") or {}).get("open"))}
                except RpcError:
                    fresh = False
                continue
            try:
                r = self.observer.call("sample", command_id=cid)
            except RpcError:
                fresh = False
                continue
            if r.get("status") != "ok" or now() - float(r.get("collected_at") or 0) > max_age_s:
                fresh = False
                continue
            out[cid] = dict(r.get("structured") or {})
        if "running_version" in out and bundle is not None:
            out["running_version"]["version_matches_expected"] = \
                out["running_version"].get("version") == bundle.deployment.get("expected_version")
        return out, fresh

    def rules_for(self, bundle, ep: dict) -> list[dict]:
        return [r for r in bundle.verifier_rules if r["applies_to"]["class"] == ep["class"]
                and ep["trigger"]["check"] in r["applies_to"].get("checks", [ep["trigger"]["check"]])]

    def check_episode(self, ep: dict) -> None:
        bundle = self.bundles.load(ep["bundle_id"])
        param = lambda pid, key=None: bundle.param(pid, key)  # noqa: E731
        max_age = float(bundle.thresholds["P-15"] * bundle.thresholds["P-01"])
        for rule in self.rules_for(bundle, ep):
            key = (ep["episode_id"], rule["id"])
            sample, fresh = self._sample(rule["samples"], max_age, bundle)
            held = fresh and evaluate(rule["predicate"], sample, param)
            self.streak[key] = self.streak.get(key, 0) + 1 if held else 0
            n, w = self.streak[key], window(rule, param)
            if not held:
                continue
            if ep["state"] == "awaiting_operator":
                if n >= w:
                    self._resolve(ep, rule, sample, n)
                    return
            elif n == 1:  # one observation per streak; state is never changed here (DD-11)
                handed_off = ep["state"] == "handed_off"
                note = "observed after hand-off; not reopened" if handed_off else "observed during analysis"
                self.store.call("append_recovery_observation", episode_id=ep["episode_id"], rule=rule["id"], note=note,
                                idem_key=f"recov:{ep['episode_id']}:{rule['id']}:{uuid.uuid4().hex}")
                if handed_off:
                    self.recovered_after_handoff.add(ep["episode_id"])
        self._maybe_escalate(ep, bundle)

    def _resolve(self, ep: dict, rule: dict, sample: dict, n: int) -> None:
        rec = self.store.call("read_episode", episode_id=ep["episode_id"], view="record")
        if rec["state"] != "awaiting_operator":
            return
        stale = [a for a in rec["annotations"] if a.get("kind") == "stale_signals"]
        self.store.call("append_verification", episode_id=ep["episode_id"], rule=rule["id"], result="pass",
                        samples=[{"n": n, "sample": sample, "stale_annotations_seen": len(stale)}],
                        idem_key=f"verif:{ep['episode_id']}:{rule['id']}:{rec['revision']}")
        rec = self.store.call("read_episode", episode_id=ep["episode_id"], view="record")
        try:
            self.store.call("set_state", episode_id=ep["episode_id"], state="resolved", expected_revision=rec["revision"],
                            reason=f"{rule['id']} held for {n} consecutive fresh samples")
        except RpcError as e:
            if e.code != "conflict":
                raise
            log.info("resolve lost a CAS race on %s; will re-evaluate", ep["episode_id"])

    def _maybe_escalate(self, ep: dict, bundle) -> None:
        if ep["state"] != "awaiting_operator" or ep["episode_id"] in self.escalated:
            return
        rec = self.store.call("read_episode", episode_id=ep["episode_id"], view="record")
        since = next((h["ts"] for h in reversed(rec["state_history"]) if h["to"] == "awaiting_operator"), None)
        deadline_s = float(bundle.param("P-17", "deadline_min")) * 60
        if since is not None and now() - since > deadline_s:
            try:
                self.report.call("system_alert", severity="high", episode_id=ep["episode_id"],
                                 title=f"Recovery not confirmed within {int(deadline_s // 60)} min",
                                 text="Episode stays awaiting_operator. The verifier does not hand off on its own.",
                                 dedupe_key=f"deadline:{ep['episode_id']}")
                self.escalated.add(ep["episode_id"])
            except RpcError as e:
                log.error("escalation alert failed: %s", e)

    def tick(self) -> None:
        for ep in self.store.call("list_episodes", nonterminal_only=False):
            if ep["state"] == "resolved":
                continue
            if ep["state"] == "handed_off" and ep["episode_id"] in self.recovered_after_handoff:
                continue
            try:
                self.check_episode(ep)
            except Exception:  # noqa: BLE001
                log.exception("verifier failed on %s", ep["episode_id"])

    def loop(self, stop: threading.Event, interval_s: float) -> None:
        while not stop.wait(interval_s):
            try:
                self.tick()
            except RpcError as e:
                log.error("verifier tick: %s", e)
