"""Sentinel scheduler [1] + telemetry checks [10] (HLD §5.1, §5.9, W11).

Runs in the trusted controller process class (it writes through store-control). Each tick:
sample the validator through the observer broker's system socket, evaluate the pure rules,
open or update episodes (the store de-duplicates per class/check/validator under its
lock), attach the samples as signals, and annotate stale validator-health episodes (TH-3).
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid

from ..audit.client import AuditClient
from ..bundle.registry import BundleRegistry
from ..common.rpc import RpcClient, RpcError
from ..consensus import determine
from .checks import ConsecutiveCounter, Finding, stale_checks, summarise, telemetry_findings, validator_findings

log = logging.getLogger(__name__)

VALIDATOR_SAMPLES = ("host_metrics", "catchup", "identity_balance", "running_version", "rpc_latency")
MODE_SAMPLES = ("running_version", "cluster_feature_state", "consensus_state_files")


class Sentinel:
    def __init__(self, store_control: RpcClient, observer_system: RpcClient, report_system: RpcClient,
                 audit: AuditClient, bundles: BundleRegistry, *, watchtower_heartbeat: str | None = None):
        # The sentinel keeps running in every degraded tier except "ops host down" (HLD §9).
        self.store = store_control
        self.observer = observer_system
        self.report = report_system
        self.audit = audit
        self.bundles = bundles
        self.watchtower_heartbeat = watchtower_heartbeat
        self.counter = ConsecutiveCounter()
        self._annotated: set[tuple[str, str]] = set()

    def _sample(self, cid: str) -> dict:
        try:
            return self.observer.call("sample", command_id=cid)
        except RpcError as e:
            return {"command_id": cid, "status": "unreachable", "structured": {"error": e.code}}

    def _watchtower_age(self) -> float | None:
        if not self.watchtower_heartbeat:
            return None
        try:
            return time.time() - os.stat(self.watchtower_heartbeat).st_mtime
        except FileNotFoundError:
            return float("inf")

    def tick(self) -> list[dict]:
        bundle_id = self.bundles.active()
        if not bundle_id:
            log.error("no active bundle; sentinel idle")
            return []
        bundle = self.bundles.load(bundle_id)
        try:
            probe = self.observer.call("probe")
        except RpcError as e:
            probe = {"reachable": False, "error": f"observer broker: {e.code}"}
        samples = {cid: self._sample(cid) for cid in VALIDATOR_SAMPLES} if probe.get("reachable") else {}
        try:
            telemetry = self.observer.call("telemetry")
        except RpcError:
            telemetry = {"consecutive_unreachable": 99}
        findings = validator_findings(samples, bundle, self.counter) + \
            telemetry_findings(telemetry, probe, bundle, self._watchtower_age())
        opened = [self._open(f, bundle, samples, telemetry) for f in findings]
        self._annotate_stale(telemetry, bundle)
        self.audit.submit("sentinel", None, {"findings": [f.check for f in findings], "reachable": probe.get("reachable")})
        return [o for o in opened if o]

    def _mode(self, bundle, samples: dict) -> tuple[str, dict]:
        extra = {cid: samples.get(cid) or self._sample(cid) for cid in MODE_SAMPLES}
        return determine(bundle.deployment["declared_consensus_mode"], extra["running_version"],
                         extra["cluster_feature_state"], extra["consensus_state_files"],
                         bundle.deployment.get("mode_support") or {})

    def _open(self, f: Finding, bundle, samples: dict, telemetry: dict) -> dict | None:
        if f.cls == "validator_health":
            mode, evidence = self._mode(bundle, samples)
        else:
            mode, evidence = "unknown", {"note": "not determined for telemetry-health episodes (observer impaired)"}
        vid = bundle.deployment["validator_id"]
        try:
            res = self.store.call("open_episode", **{
                "class": f.cls, "trigger": {"source": "sentinel", "check": f.check, "severity": f.severity, "detail": f.detail},
                "validator_id": vid, "bundle_id": bundle.id, "consensus_mode": mode, "consensus_mode_evidence": evidence,
                "idem_key": f"open:{f.cls}:{f.check}:{vid}:{uuid.uuid4().hex}"})
        except RpcError as e:
            log.error("open_episode failed: %s", e)
            return None
        eid = res["episode_id"]
        snaps = [samples[c] for c in f.command_ids if c in samples]
        if f.cls == "telemetry_health":
            snaps.append({"command_id": "telemetry_health", "status": "ok", "structured": telemetry})
        for s in snaps:
            try:
                self.store.call("append_signal", episode_id=eid, snapshot=summarise(s),
                                idem_key=f"sig:{s.get('command_id')}:{s.get('request_id') or uuid.uuid4().hex}")
            except RpcError as e:
                log.warning("append_signal failed: %s", e)
        if not res.get("deduplicated") and mode == "unknown" and f.cls == "validator_health":
            self._alert("warning", f"Consensus mode unknown for episode {eid[:8]}",
                        f"Inputs disagree: {evidence.get('disagreeing_inputs')}. Mode-specific recommendations are prohibited.",
                        eid, f"mode-unknown:{eid}")
        return res

    def _annotate_stale(self, telemetry: dict, bundle) -> None:
        stale = stale_checks(telemetry, bundle)
        if not stale:
            return
        try:
            eps = self.store.call("list_episodes", nonterminal_only=True, **{"class": "validator_health"})
        except RpcError:
            return
        for ep in eps:
            key = (ep["episode_id"], ",".join(stale))
            if key in self._annotated:
                continue
            try:
                self.store.call("annotate", episode_id=ep["episode_id"], kind="stale_signals",
                                note=f"TH-3: samples stale for {stale}; recovery cannot be confirmed from stale data",
                                idem_key=f"stale:{uuid.uuid4().hex}")
                self._annotated.add(key)
            except RpcError:
                pass

    def _alert(self, severity: str, title: str, text: str, episode_id: str | None, dedupe: str) -> None:
        try:
            self.report.call("system_alert", severity=severity, title=title, text=text, episode_id=episode_id, dedupe_key=dedupe)
        except RpcError as e:
            log.error("alert failed: %s", e)

    def loop(self, stop: threading.Event) -> None:
        while not stop.is_set():
            interval = 60.0
            try:
                active = self.bundles.active()
                if active:
                    interval = float(self.bundles.load(active).thresholds["P-01"])
                self.tick()
            except Exception:  # noqa: BLE001 - the sentinel must keep running
                log.exception("sentinel tick failed")
            stop.wait(interval)
