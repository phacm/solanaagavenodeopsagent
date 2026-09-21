"""report-broker [8] (HLD §4.1, §5.7 reporter, plan §2.6 AW-2/AW-3/AW-5).

* Reports are stored content-addressed; the store records only the ref.
* The AW-2 alert fields (severity, fault class or "outside supported classes", top-ranked
  hypothesis, recommendation or no-action, Judge verdict, report link) are filled by the
  broker FROM THE EPISODE RECORD. The reporter model supplies only a short summary, which
  is labelled model-written. A persuaded model cannot misstate the verdict in the alert.
* AW-3: unacknowledged alerts are re-sent once after P-20, then escalated to the backup.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from ..bundle.registry import BundleRegistry
from ..common.canonical import now, sha256_hex
from ..common.rpc import Ctx, Endpoint, RpcClient, RpcError
from ..common.tokens import TokenGate
from .alerts import AlertSink
from .base import BrokerBase

log = logging.getLogger(__name__)
MAX_ALERTS_PER_HOUR = 60  # alert-rate anomaly guard (HLD §4.3 "alert-rate anomalies are monitored")


class ReportBroker(BrokerBase):
    name = "report_broker"

    def __init__(self, gate: TokenGate, audit, store_agent_report_sock: str, bundles: BundleRegistry, sink: AlertSink,
                 state_dir: str | Path, *, ack_window_s: float, development: bool = False):
        super().__init__(gate, audit)
        self.store = RpcClient(store_agent_report_sock)
        self.bundles = bundles
        self.sink = sink
        self.dir = Path(state_dir)
        (self.dir / "reports").mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / "alerts.jsonl"
        self.ack_window_s = ack_window_s
        self.development = development
        self._lock = threading.Lock()
        self.alerts: dict[str, dict] = {}
        self._sent_times: list[float] = []
        self._load()

    # --- persistence -----------------------------------------------------------------
    def _load(self) -> None:
        if not self.log_path.exists():
            return
        for line in self.log_path.read_text().splitlines():
            ev = json.loads(line)
            if ev["ev"] == "sent":
                self.alerts[ev["alert"]["alert_id"]] = ev["alert"]
            elif ev["alert_id"] in self.alerts:
                self.alerts[ev["alert_id"]].update(ev["update"])

    def _log(self, ev: dict) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(ev) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _dispatch(self, alert: dict, target: str = "primary") -> dict:
        with self._lock:
            t = now()
            self._sent_times = [x for x in self._sent_times if t - x < 3600]
            if len(self._sent_times) >= MAX_ALERTS_PER_HOUR and alert.get("severity") != "critical":
                self._audit("alert", None, {"what": "alert rate cap reached; alert suppressed", "title": alert.get("title")})
                raise RpcError("rate_limited", "alert rate cap reached")
            self._sent_times.append(t)
        alert = {**alert, "alert_id": alert.get("alert_id") or uuid.uuid4().hex, "sent_ts": now(),
                 "development": self.development}
        try:
            alert["ack"] = self.sink.send(target, alert)
        except Exception as e:  # noqa: BLE001
            raise RpcError("alert_failed", f"{type(e).__name__}") from e
        alert.update({"acked": False, "resent": False, "escalated": False})
        with self._lock:
            self.alerts[alert["alert_id"]] = alert
            self._log({"ev": "sent", "alert": alert})
        self._audit("alert", None, {"alert_id": alert["alert_id"], "episode_id": alert.get("episode_id"),
                                    "kind": alert.get("kind"), "severity": alert.get("severity")})
        return alert

    # --- worker socket ---------------------------------------------------------------
    def write_incident_report(self, ctx: Ctx, p: dict) -> Any:
        cap, args = self.authorize(p, "write_incident_report")
        self.quota.take((cap.session_id, "reports"), 4)
        body = args["markdown"].encode()
        h = sha256_hex(body)
        path = self.dir / "reports" / f"{h}.md"
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(body)
            os.replace(tmp, path)
        ref = f"report:sha256:{h}"
        self.store.call("append_report", token=p["token"], episode_id=cap.episode_id, kind=args["kind"], ref=ref,
                        idem_key=f"{cap.session_id}:report:{args['kind']}:{h[:16]}")
        self._audit("tool_result", cap, {"tool": "write_incident_report", "ref": ref})
        return {"ref": ref}

    def send_alert(self, ctx: Ctx, p: dict) -> Any:
        cap, args = self.authorize(p, "send_alert")
        with self._lock:
            for a in self.alerts.values():
                if a.get("session_id") == cap.session_id and a.get("kind") == args["kind"]:
                    return {"alert_id": a["alert_id"], "ack": a["ack"], "duplicate": True}
        rec = self.store.call("read_episode", token=p["token"], episode_id=cap.episode_id)
        reports = [r for r in rec["reports"] if r["kind"] == args["kind"]]
        if not reports:
            raise RpcError("contract", "write the report before sending its alert (the alert links to it)")
        alert = self.compose(rec, args["kind"], args["summary"], reports[-1]["ref"], self.bundles.load(cap.bundle_id))
        alert["session_id"] = cap.session_id
        sent = self._dispatch(alert)
        return {"alert_id": sent["alert_id"], "ack": sent["ack"]}

    @staticmethod
    def compose(rec: dict, kind: str, summary: str, report_ref: str, bundle) -> dict:
        trig = rec["trigger"] or {}
        fc = (bundle.fault_classes.get("by_check") or {}).get(trig.get("check"))
        top = rec.get("top_hypothesis")
        rec_txt = None
        if rec["recommendations"] or rec["no_action"]:
            last = max(rec["recommendations"] + rec["no_action"], key=lambda x: x["rev"])
            rec_txt = f"{last['id']}: " + (last.get("action_text") or f"NO ACTION - {last.get('reason')}")
        verdicts = rec["verdicts"]
        verdict = None
        if verdicts:
            v = verdicts[-1]
            fails = [c["check"] for c in v["checks"] if c["result"] == "fail"]
            verdict = f"{v['result']} on {v['target_id']}" + (f" (failed: {', '.join(fails)})" if fails else "")
        return {
            "kind": kind, "episode_id": rec["episode_id"], "severity": trig.get("severity", "unknown"),
            "title": f"{'Closure' if kind == 'closure' else 'Incident'}: {rec['class']} / {trig.get('check')}",
            "fault_class": fc or "outside supported classes",
            "top_hypothesis": f"rank {top['rank']}: {top['claim']}" if top else "no hypothesis",
            "recommendation": rec_txt or "none", "judge_verdict": verdict or "none",
            "report": report_ref, "summary": summary[:1500], "state": rec["state"],
            "consensus_mode": rec["consensus_mode"], "opened_ts": rec.get("opened_ts"),
            "needs_ack": kind == "incident",
        }

    # --- system socket (controller, verifier) ----------------------------------------
    def system_alert(self, ctx: Ctx, p: dict) -> Any:
        sev = p.get("severity")
        if sev not in ("info", "warning", "high", "critical"):
            raise RpcError("invalid", "severity must be info|warning|high|critical")
        alert = {"kind": "system", "severity": sev, "title": str(p.get("title", ""))[:200], "text": str(p.get("text", ""))[:4000],
                 "episode_id": p.get("episode_id"), "source": ctx.principal, "needs_ack": sev in ("high", "critical")}
        dedupe = p.get("dedupe_key")
        if dedupe:
            with self._lock:
                for a in self.alerts.values():
                    if a.get("dedupe_key") == dedupe:
                        return {"alert_id": a["alert_id"], "duplicate": True}
            alert["dedupe_key"] = dedupe
        sent = self._dispatch(alert)
        return {"alert_id": sent["alert_id"], "ack": sent["ack"]}

    def alerts_for(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            return [a for a in self.alerts.values() if a.get("episode_id") == p.get("episode_id")
                    and (p.get("session_id") is None or a.get("session_id") == p.get("session_id"))]

    # --- operator socket -------------------------------------------------------------
    def ack(self, ctx: Ctx, p: dict) -> Any:
        aid = p.get("alert_id")
        with self._lock:
            a = self.alerts.get(aid)
            if a is None:
                raise RpcError("not_found", "no such alert")
            upd = {"acked": True, "acked_ts": now(), "acked_by": ctx.principal}
            a.update(upd)
            self._log({"ev": "update", "alert_id": aid, "update": upd})
        self._audit("alert", None, {"alert_id": aid, "acked": True})
        return {"ok": True}

    def list_alerts(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            return sorted(self.alerts.values(), key=lambda a: a["sent_ts"])[-int(p.get("limit", 50)):]

    # --- AW-3 escalation -------------------------------------------------------------
    def escalate_tick(self) -> None:
        t = now()
        for a in list(self.alerts.values()):
            if not a.get("needs_ack") or a.get("acked") or a.get("escalated"):
                continue
            age = t - a["sent_ts"]
            if not a["resent"] and age > self.ack_window_s:
                try:
                    self.sink.send("primary", {**a, "title": "RE-SENT (unacknowledged): " + a.get("title", "")})
                except Exception as e:  # noqa: BLE001
                    log.error("re-send failed: %s", e)
                    continue
                self._update(a, {"resent": True, "resent_ts": t})
            elif a["resent"] and t - a.get("resent_ts", t) > self.ack_window_s:
                try:
                    self.sink.send("backup", {**a, "title": "ESCALATED to backup operator: " + a.get("title", "")})
                except Exception as e:  # noqa: BLE001
                    log.error("escalation failed: %s", e)
                    continue
                self._update(a, {"escalated": True, "escalated_ts": t})

    def _update(self, a: dict, upd: dict) -> None:
        with self._lock:
            a.update(upd)
            self._log({"ev": "update", "alert_id": a["alert_id"], "update": upd})
        self._audit("alert", None, {"alert_id": a["alert_id"], **{k: v for k, v in upd.items() if isinstance(v, bool)}})

    def escalate_loop(self, stop: threading.Event, interval_s: float = 30) -> None:
        while not stop.wait(interval_s):
            self.escalate_tick()

    def endpoints(self, sock_dir: str, worker_uids: set[int], system_uids: set[int], controller_uids: set[int],
                  operator_uids: set[int]) -> list[Endpoint]:
        return [
            Endpoint("report-broker", f"{sock_dir}/worker.sock", "worker", worker_uids,
                     {"write_incident_report": self.write_incident_report, "send_alert": self.send_alert}),
            Endpoint("report-broker-system", f"{sock_dir}/system.sock", "system", system_uids,
                     {"system_alert": self.system_alert, "alerts_for": self.alerts_for}),
            Endpoint("report-broker-operator", f"{sock_dir}/operator.sock", "operator", operator_uids,
                     {"ack": self.ack, "list_alerts": self.list_alerts}),
            self.admin_endpoint(f"{sock_dir}/admin.sock", controller_uids),
        ]
