"""Controller [2] -- episode runner (HLD §5.2, §5.8, §7.2, §7.3, W12).

Deterministic state machine. It decides which step runs, with what inputs, under which
budget, and whether its output counted. It reads the episode record, never transcripts
(R-9), mints one capability token per step and revokes it at step end (R-10), and moves
state only by CAS on `revision` (R-7) after artefact validation (R-8). Any exception,
budget exhaustion, integrity failure or missing artefact ends in `handed_off` + alert
(R-4). It holds no provider key.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..audit.client import AuditClient
from ..audit.sequencer import verify_chain
from ..bundle.registry import Bundle, BundleRegistry
from ..common.canonical import now
from ..common.crypto import Signer
from ..common.rpc import RpcClient, RpcError
from ..common.tokens import mint
from ..common.tools import TOOLS_BY_ROLE, TOOLS_BY_NAME
from ..sandbox.bwrap import SandboxUnavailable
from ..store.fold import top_hypothesis
from . import artefacts as A
from . import preflight as PF
from .spawn import MODEL_PORT, build_home, remove_home

log = logging.getLogger(__name__)
LIMIT_CAUSES = ("limit_requests", "limit_input_tokens", "limit_output_or_usd")


class _Early(Exception):
    """Internal: a step ended before the worker ran; still recorded as a failed step."""


@dataclass
class StepOutcome:
    ok: bool
    reason: str = ""
    limit_hit: bool = False
    meter: dict = field(default_factory=dict)


@dataclass
class ControllerDeps:
    store: RpcClient                       # store-control
    audit: AuditClient                     # controller socket; NOT buffered (RB-8)
    bundles: BundleRegistry
    token_signer: Signer
    report_sys: RpcClient
    admins: dict[str, RpcClient]           # episode_broker / observer_broker / report_broker admin sockets
    model_admin: RpcClient
    launcher: Any
    worker_sockets: dict[str, str]         # episode / observer / report worker sockets (host paths)
    steps_dir: Path
    flag: PF.ObserveOnlyFlag
    chain_path: Path | None = None
    anchor_store: Any = None
    anchor_keys: dict | None = None
    development: bool = False


class Runner:
    def __init__(self, d: ControllerDeps):
        self.d = d
        self._alerted: set[str] = set()
        self.last_preflight: PF.Preflight | None = None

    # --- alerts / audit --------------------------------------------------------------
    def alert(self, severity: str, title: str, text: str = "", episode_id: str | None = None, dedupe: str | None = None) -> None:
        try:
            self.d.report_sys.call("system_alert", severity=severity, title=title, text=text, episode_id=episode_id,
                                   dedupe_key=dedupe)
        except RpcError as e:
            log.error("alert failed (%s): %s", e.code, title)

    def _audit(self, event: str, episode_id: str | None, data: dict, payload: Any = None) -> None:
        try:
            self.d.audit.submit(event, episode_id, data, payload)
        except RpcError as e:
            log.error("audit submit failed: %s", e)

    # --- store helpers ---------------------------------------------------------------
    def record(self, eid: str) -> dict:
        return self.d.store.call("read_episode", episode_id=eid, view="record")

    def transition(self, rec: dict, to: str, reason: str = "") -> bool:
        try:
            self.d.store.call("set_state", episode_id=rec["episode_id"], state=to, expected_revision=rec["revision"],
                              reason=reason, idem_key=f"state:{rec['revision']}:{to}")
        except RpcError as e:
            if e.code == "conflict":  # R-7: re-read and re-decide next tick
                log.info("CAS conflict on %s -> %s; will re-decide", rec["episode_id"], to)
                return False
            raise
        self._audit("state_change", rec["episode_id"], {"from": rec["state"], "to": to, "reason": reason})
        return True

    def hand_off(self, rec: dict, reason: str, severity: str = "high") -> None:
        if self.transition(rec, "handed_off", reason):
            self.alert(severity, f"Episode handed off: {reason[:120]}",
                       f"Episode {rec['episode_id']} ({rec['class']}/{rec['trigger']['check']}) handed to the operator. "
                       f"No action is taken by the system. Reason: {reason}", rec["episode_id"], f"handoff:{rec['episode_id']}")

    # --- pre-flight ------------------------------------------------------------------
    def preflight(self) -> PF.Preflight:
        active = self.d.bundles.active()
        th = self.d.bundles.load(active).thresholds if active and not self.d.bundles.verify(active) else None
        pf = PF.run(flag=self.d.flag, bundles=self.d.bundles, audit_status=self.d.audit.status,
                    brokers={"model_broker": self.d.model_admin, **self.d.admins}, launcher=self.d.launcher,
                    anchor_interval_s=(th["P-18"] * 60) if th else 900, max_anchor_lag_s=(th["P-19"] * 60) if th else 3600)
        for r in pf.observe_only:
            if "fails verification" in r or "audit chain" in r:
                self.d.flag.set(r)
        for r in pf.observe_only + pf.no_llm:
            key = "pf:" + r.split(":")[0]
            if key not in self._alerted:
                self.alert("critical" if r in pf.observe_only else "high", f"Degraded: {r[:120]}", r, dedupe=None)
                self._alerted.add(key)
        for r in pf.warnings:
            if "pf:lag" not in self._alerted:
                self.alert("warning", r, r)
                self._alerted.add("pf:lag")
        if pf.llm_allowed:
            self._alerted = {k for k in self._alerted if not k.startswith("pf:")}
        self.last_preflight = pf
        return pf

    def verify_chain_now(self) -> dict | None:
        if not self.d.chain_path or self.d.anchor_store is None:
            return None
        res = verify_chain(self.d.chain_path, self.d.anchor_store.list(), self.d.anchor_keys or {})
        if not res["ok"]:
            self.d.flag.set("chain verification failed: " + "; ".join(res["errors"][:3]))
            self.alert("critical", "Audit chain verification FAILED (RB-10)", "\n".join(res["errors"][:20]), dedupe=None)
        return res

    # --- step execution --------------------------------------------------------------
    def input_view(self, rec: dict, role: str, bundle: Bundle) -> dict:
        if role == "proposal_judge":
            view = self.d.store.call("read_episode", episode_id=rec["episode_id"], view="judge")
            A.assert_judge_isolated(view, rec)
            return view
        return self.d.store.call("read_episode", episode_id=rec["episode_id"], view="full")

    def run_step(self, rec: dict, role: str, bundle: Bundle, kind: str = "incident") -> StepOutcome:
        eid = rec["episode_id"]
        session = str(uuid.uuid4())
        conf_name, conf = bundle.configuration_for(role)
        ttl = float(bundle.thresholds["P-10"])
        token = mint(self.d.token_signer, episode_id=eid, role=role, session_id=session, bundle_id=bundle.id, ttl_s=ttl)
        self._audit("token_minted", eid, {"role": role, "session_id": session, "ttl_s": ttl, "configuration": conf_name})
        home = None
        meter: dict = {}
        res = None
        early: StepOutcome | None = None
        try:
            try:
                ms = self.d.model_admin.call("open_session", session_id=session, episode_id=eid, role=role, bundle_id=bundle.id)
            except RpcError as e:
                # Unapproved or unadmitted configuration is not retried (it cannot succeed).
                early = StepOutcome(False, f"model broker refused session: {e.code} {e.message}",
                                    limit_hit=e.code in ("provider_unapproved", "not_admitted", "no_key"))
                ms = None
            if early is not None:
                raise _Early()
            view = self.input_view(rec, role, bundle)
            inlined = conf["adapter"] != "claude_sdk" or bool(bundle.deployment.get("skills_inline", True))
            spec = {
                "role": role, "episode_id": eid, "session_id": session, "token": token, "kind": kind,
                "state": rec["state"], "bundle_path": "/bundle", "inlined_prompts": inlined,
                "configuration": {"name": conf_name, **conf}, "model_port": MODEL_PORT,
                "sockets": {"episode": "/run/valops/episode.sock", "observer": "/run/valops/observer.sock",
                            "report": "/run/valops/report.sock", "model": "/run/valops/model.sock"},
                "tools": TOOLS_BY_ROLE[role], "max_turns": int(bundle.param("P-05", role, conf_name)),
                "max_budget_usd": float(bundle.param("P-06", role, conf_name)),
                "tool_states": {t: list(TOOLS_BY_NAME[t].states) for t in TOOLS_BY_ROLE[role]},
                "input_view": view, "development": self.d.development,
                "timeout_s": max(30.0, float(bundle.thresholds["P-11"]) - 20),
            }
            prompt = bundle.prompt_path(role, inlined).read_text()
            home = build_home(self.d.steps_dir, session, spec, prompt, conf["adapter"])
            sockets = {**self.d.worker_sockets, "model": ms["socket_path"]}
            try:
                res = self.d.launcher.run(adapter=conf["adapter"], home=home, bundle_dir=bundle.path, sockets=sockets,
                                          timeout_s=float(bundle.thresholds["P-11"]))
            except SandboxUnavailable as e:
                early = StepOutcome(False, f"sandbox unavailable: {e}")
                raise _Early() from e
            self._audit("step", eid, {"role": role, "session_id": session, "exit": res.exit_code, "timed_out": res.timed_out},
                        payload=res.stderr or None)
        except _Early:
            pass
        finally:
            for name, admin in self.d.admins.items():
                try:
                    admin.call("revoke_session", session_id=session)
                except RpcError as e:
                    log.error("revoke at %s failed: %s", name, e)
            try:
                meter = self.d.model_admin.call("close_session", session_id=session) if ms else {}
            except RpcError:
                meter = {}
            self._audit("token_revoked", eid, {"session_id": session})
            if meter:
                try:
                    self.d.store.call("append_cost", episode_id=eid, role=role, usd=float(meter.get("usd", 0.0)),
                                      turns=int(meter.get("requests", 0)), session_id=session, configuration=conf_name,
                                      tokens={"input": meter.get("input_tokens"), "output": meter.get("output_tokens")},
                                      idem_key=f"cost:{session}")
                except RpcError as e:
                    log.error("append_cost failed: %s", e)
            if home is not None:
                remove_home(home)
        limit_hit = any(r["cause"] in LIMIT_CAUSES for r in meter.get("refusals", []))
        if early is not None:
            out = early
        elif res.timed_out:
            out = StepOutcome(False, f"step exceeded P-11 ({bundle.thresholds['P-11']}s); process tree killed", meter=meter)
        else:
            out = self.validate(role, eid, session, kind, res.structured_output)
            out.meter = meter
        if limit_hit and not out.ok:
            out.limit_hit, out.reason = True, out.reason + "; model-broker budget/limit reached"
        self.d.store.call("append_step", episode_id=eid, role=role, session_id=session,
                          outcome="ok" if out.ok else "failed", reason=out.reason, state=rec["state"],
                          configuration=conf_name, idem_key=f"step:{session}")
        return out

    def validate(self, role: str, eid: str, session: str, kind: str, structured: dict | None) -> StepOutcome:
        rec = self.record(eid)
        if role == "diagnostician":
            v, stored = A.validate_diagnostician(rec, session)
        elif role == "change_planner":
            v, stored = A.validate_planner(rec, session)
        elif role == "proposal_judge":
            v, stored = A.validate_judge(rec, session)
        else:
            alerts = self.d.report_sys.call("alerts_for", episode_id=eid, session_id=session)
            v, stored = A.validate_reporter(rec, session, kind, alerts)
        if not v.ok:
            return StepOutcome(False, v.reason)
        c = A.cross_check(role, structured, stored)
        return StepOutcome(c.ok, c.reason)

    # --- state machine ---------------------------------------------------------------
    @staticmethod
    def _failures_in_state(rec: dict, role: str) -> list[dict]:
        entered = rec["state_history"][-1]["ts"]
        return [s for s in rec["steps"] if s["role"] == role and s["outcome"] == "failed" and s["ts"] >= entered]

    def _after_failure(self, rec: dict, role: str, out: StepOutcome, bundle: Bundle) -> None:
        rec = self.record(rec["episode_id"])
        if out.limit_hit:
            self.hand_off(rec, f"{role}: not retryable - {out.reason}")  # RB-2 / MB-5: limits and refusals are not retried
            return
        fails = self._failures_in_state(rec, role)
        if len(fails) > int(bundle.thresholds["P-08"]):
            self.hand_off(rec, f"{role}: step failed {len(fails)}x; last: {out.reason}")

    def _bundle_problem(self, rec: dict) -> bool:
        reason = self.d.bundles.verify(rec["bundle_id"])
        if reason:
            if "revoked" in reason:
                self.hand_off(rec, f"bound bundle revoked (RB-4): {reason}", "critical")
            else:
                self.d.flag.set(f"bound bundle {rec['bundle_id'][:12]} fails verification: {reason}")
                self.alert("critical", "Bundle integrity failure: observe-only (RB-3)", reason, rec["episode_id"],
                           f"integrity:{rec['bundle_id']}")
            return True
        sup = self.d.bundles.superseded_at(rec["bundle_id"])
        if sup is not None and rec["state"] not in ("resolved", "handed_off"):
            bundle = self.d.bundles.load(rec["bundle_id"])
            if now() - sup > float(bundle.thresholds["P-12"]) * 3600:
                self.hand_off(rec, "bundle drain deadline exceeded (P-12)")
                return True
        return False

    def advance(self, eid: str, pf: PF.Preflight) -> None:
        rec = self.record(eid)
        state = rec["state"]
        if state == "handed_off" or state == "awaiting_operator":
            return
        if self._bundle_problem(rec):
            return
        bundle = self.d.bundles.load(rec["bundle_id"])
        if state == "resolved":
            self._closure(rec, bundle, pf)
            return
        if not pf.llm_allowed:
            return  # observe-only / sentinel-and-alert tier: no LLM step starts
        if state == "open":
            self.transition(rec, "diagnosing", "bundle verified; LLM path available")
            return
        role = {"diagnosing": "diagnostician", "recommending": "change_planner",
                "judging": "proposal_judge", "reporting": "reporter"}[state]
        try:
            out = self.run_step(rec, role, bundle)
        except AssertionError as e:  # judge isolation violated: integrity failure
            self.hand_off(self.record(eid), f"judge isolation check failed: {e}", "critical")
            return
        if not out.ok:
            self._after_failure(rec, role, out, bundle)
            return
        rec = self.record(eid)
        if state == "diagnosing":
            # Recovery observed during analysis, or nothing supports an action -> reporting.
            refuted_all = all(h["status"] == "refuted" for h in rec["hypotheses"] if h["step_session"] ==
                              (top_hypothesis(rec) or {}).get("step_session"))
            if rec["recovery_observations"] or refuted_all:
                self.transition(rec, "reporting", "recovery observed" if rec["recovery_observations"] else "all hypotheses refuted")
            else:
                self.transition(rec, "recommending", "hypotheses validated")
        elif state == "recommending":
            self.transition(rec, "judging", "artefact validated")
        elif state == "judging":
            v = rec["verdicts"][-1]
            if v["result"] == "PASS":
                self.transition(rec, "reporting", "Judge PASS")
                return
            fails = [x for x in rec["verdicts"] if x["result"] == "FAIL"]
            if len(fails) <= int(bundle.thresholds["P-09"]):
                self.transition(rec, "recommending", f"Judge FAIL {len(fails)}/{bundle.thresholds['P-09']}")
            else:
                reasons = "; ".join(f"{x['target_id']}: " + ", ".join(c["check"] for c in x["checks"] if c["result"] == "fail")
                                    for x in fails)
                self.hand_off(rec, f"Judge FAIL retries exhausted (R-3). FAIL reasons: {reasons}")
        elif state == "reporting":
            self.transition(rec, "awaiting_operator", "report written and alert dispatched")

    def _closure(self, rec: dict, bundle: Bundle, pf: PF.Preflight) -> None:
        """FR-15: after `resolved`, one closure reporter step. The state never changes."""
        if any(r["kind"] == "closure" for r in rec["reports"]):
            return
        fails = [s for s in rec["steps"] if s["role"] == "reporter" and s.get("state") == "resolved" and s["outcome"] == "failed"]
        if len(fails) > int(bundle.thresholds["P-08"]):
            self.alert("warning", "Closure report could not be produced", f"episode {rec['episode_id']}", rec["episode_id"],
                       f"closure-failed:{rec['episode_id']}")
            return
        if not pf.llm_allowed:
            return
        self.run_step(rec, "reporter", bundle, kind="closure")

    def tick(self) -> None:
        pf = self.preflight()
        try:
            eps = self.d.store.call("list_episodes", nonterminal_only=False)
        except RpcError as e:
            log.error("store unavailable: %s", e)  # RB-7
            self.alert("high", "Episode store unavailable (RB-7)", str(e), dedupe=None)
            return
        for ep in eps:
            if ep["state"] == "handed_off":
                continue
            try:
                self.advance(ep["episode_id"], pf)
            except RpcError as e:
                log.error("advance %s: %s", ep["episode_id"], e)
                if e.code in ("unavailable", "audit_unavailable"):
                    continue  # nothing assumed written; idempotent retry next tick
                try:
                    self.hand_off(self.record(ep["episode_id"]), f"controller error: {e.code} {e.message}")
                except RpcError:
                    pass
            except Exception as e:  # noqa: BLE001 - R-4: never a silent stop
                log.exception("advance %s failed", ep["episode_id"])
                try:
                    self.hand_off(self.record(ep["episode_id"]), f"controller exception: {type(e).__name__}")
                except RpcError:
                    pass

    def loop(self, stop: threading.Event, interval_s: float = 5.0, chain_verify_every_s: float = 900) -> None:
        last_verify = 0.0
        while not stop.is_set():
            if now() - last_verify > chain_verify_every_s:
                try:
                    self.verify_chain_now()
                except Exception:  # noqa: BLE001
                    log.exception("chain verification error")
                last_verify = now()
            self.tick()
            stop.wait(interval_s)
