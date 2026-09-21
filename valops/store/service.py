"""Episode Store [3s] (HLD §5.3, W3). Source of truth (DD-1).

Endpoints differ in WHICH OPERATIONS EXIST, not only in what they permit (DD-8):

  store-agent    episode_broker, capability token required
                 append_hypothesis, append_hypothesis_status, append_recommendation,
                 append_no_action, append_verdict, read_episode
  store-agent-report  report_broker, capability token required: append_report, read_episode
                 -- neither agent socket has set_state, append_verification or closure.
  store-control  controller only
                 open_episode, set_state (every state except resolved), append_signal,
                 append_cost, append_step, annotate, read_episode, list_episodes
  store-verify   verifier only
                 append_verification, append_recovery_observation,
                 set_state(resolved, only from awaiting_operator), read_episode, list_episodes
  store-observe  observer_broker only (implementation note N-1, docs/IMPLEMENTATION-NOTES.md)
                 append_observation: a tool-driven re-sample becomes a citable signal. The
                 content comes from the daemon via the broker, never from the worker.

Terminal episodes accept only reports (closure), recovery observations (§7.3) and the
controller's bookkeeping (cost, step, annotation); no transition and no other write.

Invariants: append-only (SQLite triggers forbid UPDATE/DELETE); every write carries an
idempotency key; every transition is CAS on `revision`; every write records the
authenticated principal, session, bound bundle and an audit reference; contract checks
are server-side.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from ..audit.client import AuditClient
from ..bundle.registry import BundleRegistry
from ..common.canonical import now, sha256_obj
from ..common.rpc import Ctx, Endpoint, RpcError
from ..common.schema import SchemaError, validate
from ..common.tokens import Capability, TokenGate
from ..common.tools import TOOLS_BY_NAME
from . import transitions
from .fold import VIEW_BY_ROLE, apply, empty_record, view_for

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries(
  episode_id TEXT NOT NULL, rev INTEGER NOT NULL, ts REAL NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
  principal TEXT NOT NULL, session_id TEXT, bundle_id TEXT NOT NULL, audit_ref TEXT NOT NULL,
  idem_key TEXT NOT NULL, result TEXT NOT NULL,
  PRIMARY KEY(episode_id, rev), UNIQUE(episode_id, idem_key));
CREATE TABLE IF NOT EXISTS opens(idem_key TEXT PRIMARY KEY, episode_id TEXT NOT NULL, result TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS entries_no_update BEFORE UPDATE ON entries BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS entries_no_delete BEFORE DELETE ON entries BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS opens_no_update BEFORE UPDATE ON opens BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS opens_no_delete BEFORE DELETE ON opens BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""

CLASSES = ("validator_health", "telemetry_health")
MODES = ("tower", "alpenglow", "unknown")
# agent operation -> (tool whose role/state rules apply, entry kind)
AGENT_OPS = {
    "append_hypothesis": "add_hypothesis",
    "append_hypothesis_status": "set_hypothesis_status",
    "append_recommendation": "propose_recommendation",
    "append_no_action": "report_no_action",
    "append_verdict": "submit_verdict",
    "append_report": "write_incident_report",
}


def _nonempty(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


class EpisodeStore:
    def __init__(self, db_path: str | Path, bundles: BundleRegistry, tokens: TokenGate, audit: AuditClient | None):
        self.bundles = bundles
        self.tokens = tokens
        self.audit = audit
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(SCHEMA)
        self._records: dict[str, dict] = {}
        self._rebuild()

    # --- persistence -----------------------------------------------------------------
    def _rebuild(self) -> None:
        rows = self._db.execute(
            "SELECT episode_id, rev, ts, kind, body, principal, session_id, bundle_id, audit_ref FROM entries ORDER BY episode_id, rev")
        for r in rows:
            e = self._row(r)
            rec = self._records.setdefault(e["episode_id"], empty_record(e["episode_id"]))
            apply(rec, e)

    @staticmethod
    def _row(r: tuple) -> dict:
        return {"episode_id": r[0], "rev": r[1], "ts": r[2], "kind": r[3], "body": json.loads(r[4]),
                "principal": r[5], "session_id": r[6], "bundle_id": r[7], "audit_ref": r[8]}

    def _record(self, episode_id: str) -> dict:
        rec = self._records.get(episode_id)
        if rec is None:
            raise RpcError("not_found", "no such episode")
        return rec

    def _idem(self, episode_id: str, idem_key: Any) -> Any:
        if not _nonempty(idem_key) or len(idem_key) > 200:
            raise RpcError("invalid", "idem_key required")
        row = self._db.execute("SELECT result FROM entries WHERE episode_id=? AND idem_key=?", (episode_id, idem_key)).fetchone()
        return json.loads(row[0]) if row else None

    def _append(self, rec: dict, kind: str, body: dict, *, principal: str, session_id: str | None,
                idem_key: str, result: Any) -> Any:
        rev = rec["revision"] + 1
        ts = now()
        audit_ref = "audit:none"
        if self.audit is not None:
            try:
                r = self.audit.submit("store_write", rec["episode_id"], {
                    "kind": kind, "rev": rev, "principal": principal, "session_id": session_id,
                    "bundle_id": rec["bundle_id"], "entry_hash": sha256_obj(body)})
                audit_ref = self.audit.ref(r)
            except RpcError as e:
                raise RpcError("audit_unavailable", str(e)) from e
        self._db.execute(
            "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rec["episode_id"], rev, ts, kind, json.dumps(body, sort_keys=True), principal, session_id,
             rec["bundle_id"], audit_ref, idem_key, json.dumps(result)))
        apply(rec, {"episode_id": rec["episode_id"], "rev": rev, "ts": ts, "kind": kind, "body": body,
                    "principal": principal, "session_id": session_id, "audit_ref": audit_ref})
        return result

    @staticmethod
    def _next_id(items: list, prefix: str) -> str:
        return f"{prefix}{len(items) + 1}"

    # --- shared checks ---------------------------------------------------------------
    @staticmethod
    def _refs_exist(rec: dict, refs: Any, *, required: bool = True) -> list[str]:
        if not isinstance(refs, list) or (required and not refs):
            raise RpcError("contract", "evidence_refs must be a non-empty list of collected signal ids")
        have = {s["id"] for s in rec["signals"]}
        missing = [r for r in refs if r not in have]
        if missing:
            # §5.3 evidence-reference bridge: a fabricated justification is a rejected write.
            raise RpcError("contract", f"evidence_refs name signals never collected in this episode: {missing}")
        return refs

    def _agent_gate(self, ctx: Ctx, op: str, p: dict) -> tuple[Capability, dict]:
        if ctx.principal not in ("episode_broker", "report_broker"):
            raise RpcError("forbidden", "store-agent serves brokers only")
        episode_id = p.get("episode_id")
        cap = self.tokens.check(p.get("token"), episode_id=episode_id)
        rec = self._record(episode_id)
        if cap.bundle_id != rec["bundle_id"]:
            raise RpcError("bundle_refused", "token bundle differs from the episode's bound bundle")
        if op in AGENT_OPS:
            tool = TOOLS_BY_NAME[AGENT_OPS[op]]
            if cap.role not in tool.roles:
                raise RpcError("forbidden", f"role {cap.role} may not {op}")
            if rec["state"] not in tool.states:
                raise RpcError("illegal_state", f"{op} not legal in state {rec['state']}")
        return cap, rec

    # --- store-agent -----------------------------------------------------------------
    def append_hypothesis(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap, rec = self._agent_gate(ctx, "append_hypothesis", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            h = p.get("hypothesis") or {}
            for f in ("claim", "test", "expected_evidence"):
                if not _nonempty(h.get(f)):
                    raise RpcError("contract", f"hypothesis requires a non-empty {f!r} (falsifiability contract)")
            rank = h.get("rank")
            if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                raise RpcError("contract", "rank must be a positive integer")
            if any(x["step_session"] == cap.session_id and x["rank"] == rank for x in rec["hypotheses"]):
                raise RpcError("contract", f"rank {rank} already used in this step")
            hid = self._next_id(rec["hypotheses"], "h")
            body = {"id": hid, "step_session": cap.session_id, "rank": rank,  # step_session stamped from the token
                    "claim": h["claim"], "test": h["test"], "expected_evidence": h["expected_evidence"]}
            return self._append(rec, "hypothesis", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"hypothesis_id": hid})

    def append_hypothesis_status(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap, rec = self._agent_gate(ctx, "append_hypothesis_status", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            hid, status = p.get("hypothesis_id"), p.get("status")
            if hid not in {h["id"] for h in rec["hypotheses"]}:
                raise RpcError("contract", f"no hypothesis {hid}")
            if status not in ("supported", "refuted"):
                raise RpcError("contract", "status must be supported|refuted")
            refs = self._refs_exist(rec, p.get("evidence_refs"))
            body = {"hypothesis_id": hid, "status": status, "evidence_refs": refs}
            return self._append(rec, "hypothesis_status", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"ok": True})

    def _one_per_session(self, rec: dict, cap: Capability, kinds: tuple[str, ...]) -> None:
        for k in kinds:
            if any(x.get("session_id") == cap.session_id for x in rec[k]):
                raise RpcError("contract", "this step has already recorded its artefact")

    def append_recommendation(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap, rec = self._agent_gate(ctx, "append_recommendation", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            self._one_per_session(rec, cap, ("recommendations", "no_action"))
            r = p.get("recommendation") or {}
            try:
                validate(r, TOOLS_BY_NAME["propose_recommendation"].input_schema)
            except SchemaError as e:
                raise RpcError("contract", str(e)) from e
            if r["hypothesis_id"] not in {h["id"] for h in rec["hypotheses"]}:
                raise RpcError("contract", f"no hypothesis {r['hypothesis_id']}")
            skills = self.bundles.load(rec["bundle_id"]).skills
            skill = skills.get(r["skill"])
            if skill is None or "change_planner" not in skill.get("roles", []):
                raise RpcError("contract", f"skill {r['skill']!r} is not a planner skill in the bound bundle")
            modes = skill.get("modes")
            if modes != "any":
                # §5.10: mode-specific recommendations are prohibited when mode is unknown,
                # and must match the confirmed mode otherwise. Deterministic layer in front
                # of the Judge's own check.
                if rec["consensus_mode"] == "unknown":
                    raise RpcError("contract", "consensus mode is unknown: mode-specific skills are prohibited")
                if rec["consensus_mode"] not in modes:
                    raise RpcError("contract", f"skill {r['skill']} does not apply to mode {rec['consensus_mode']}")
            self._refs_exist(rec, r["evidence_refs"])
            rid = self._next_id(rec["recommendations"], "r")
            body = {"id": rid, "hypothesis": r["hypothesis_id"], "action_text": r["action_text"], "skill": r["skill"],
                    "preconditions": r["preconditions"], "expected_postcondition": r["expected_postcondition"],
                    "evidence_refs": r["evidence_refs"]}
            return self._append(rec, "recommendation", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"recommendation_id": rid})

    def append_no_action(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap, rec = self._agent_gate(ctx, "append_no_action", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            self._one_per_session(rec, cap, ("recommendations", "no_action"))
            if not _nonempty(p.get("reason")):
                raise RpcError("contract", "no-action requires a reason")
            refs = self._refs_exist(rec, p.get("evidence_refs"))
            nid = self._next_id(rec["no_action"], "n")
            body = {"id": nid, "reason": p["reason"], "evidence_refs": refs}
            return self._append(rec, "no_action", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"no_action_id": nid})

    def append_verdict(self, ctx: Ctx, p: dict) -> Any:
        from .fold import under_judgement

        with self._lock:
            cap, rec = self._agent_gate(ctx, "append_verdict", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            self._one_per_session(rec, cap, ("verdicts",))
            target = under_judgement(rec)
            if target is None or p.get("target_id") != target["id"]:
                raise RpcError("contract", "verdict must target the artefact currently under judgement")
            if p.get("result") not in ("PASS", "FAIL"):
                raise RpcError("contract", "result must be PASS|FAIL")
            checks = p.get("checks")
            if not isinstance(checks, list) or not checks:
                raise RpcError("contract", "a verdict requires a non-empty list of checks performed")
            try:
                validate(checks, TOOLS_BY_NAME["submit_verdict"].input_schema["properties"]["checks"])
            except SchemaError as e:
                raise RpcError("contract", str(e)) from e
            body = {"target_id": target["id"], "result": p["result"], "checks": checks}
            return self._append(rec, "verdict", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"ok": True})

    def append_report(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            if ctx.principal != "report_broker":
                raise RpcError("forbidden", "reports are written through the report broker")
            cap, rec = self._agent_gate(ctx, "append_report", p)
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            kind, ref = p.get("kind"), p.get("ref")
            need = {"incident": "reporting", "closure": "resolved"}.get(kind)
            if need is None or rec["state"] != need:
                raise RpcError("illegal_state", f"a {kind} report is not legal in state {rec['state']}")
            if not _nonempty(ref) or not ref.startswith("report:sha256:"):
                raise RpcError("contract", "report ref must be a content address")
            body = {"kind": kind, "ref": ref}
            return self._append(rec, "report", body, principal=f"agent:{cap.role}", session_id=cap.session_id,
                                idem_key=p["idem_key"], result={"ok": True})

    def agent_read(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap, rec = self._agent_gate(ctx, "read_episode", p)
            view = VIEW_BY_ROLE[cap.role]  # forced by role; a requested view is ignored
            return view_for(rec, view, self.bundles.load(rec["bundle_id"]).skills)

    # --- store-control ---------------------------------------------------------------
    def open_episode(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            idem = p.get("idem_key")
            if not _nonempty(idem):
                raise RpcError("invalid", "idem_key required")
            row = self._db.execute("SELECT result FROM opens WHERE idem_key=?", (idem,)).fetchone()
            if row:
                return json.loads(row[0])
            cls, trig, vid = p.get("class"), p.get("trigger") or {}, p.get("validator_id")
            if cls not in CLASSES:
                raise RpcError("invalid", f"class must be one of {CLASSES}")
            if not all(_nonempty(trig.get(k)) for k in ("source", "check", "severity")) or not _nonempty(vid):
                raise RpcError("invalid", "trigger {source, check, severity} and validator_id required")
            if p.get("consensus_mode") not in MODES:
                raise RpcError("invalid", "consensus_mode must be tower|alpenglow|unknown")
            bundle_id = p.get("bundle_id")
            reason = self.bundles.verify(bundle_id)
            if reason:
                raise RpcError("bundle_refused", reason)
            dedupe_key = f"{cls}|{trig['check']}|{vid}"
            for rec in self._records.values():
                if rec.get("dedupe_key") == dedupe_key and rec["state"] not in transitions.TERMINAL:
                    # One open episode per (class, check, validator): a repeat signal updates it.
                    result = {"episode_id": rec["episode_id"], "deduplicated": True}
                    self._db.execute("INSERT INTO opens VALUES (?,?,?)", (idem, rec["episode_id"], json.dumps(result)))
                    return result
            eid = str(uuid.uuid4())
            rec = empty_record(eid)
            rec["bundle_id"] = bundle_id
            self._records[eid] = rec
            body = {"class": cls, "trigger": trig, "validator_id": vid, "bundle_id": bundle_id,
                    "consensus_mode": p["consensus_mode"], "consensus_mode_evidence": p.get("consensus_mode_evidence") or {},
                    "dedupe_key": dedupe_key}
            result = {"episode_id": eid, "deduplicated": False}
            try:
                self._append(rec, "opened", body, principal=ctx.principal, session_id=None, idem_key=idem, result=result)
            except Exception:
                del self._records[eid]
                raise
            self._db.execute("INSERT INTO opens VALUES (?,?,?)", (idem, eid, json.dumps(result)))
            return result

    def set_state(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            rec = self._record(p.get("episode_id"))
            prior = self._idem(rec["episode_id"], p.get("idem_key") or f"state:{p.get('expected_revision')}:{p.get('state')}")
            if prior is not None:
                return prior
            to, expected = p.get("state"), p.get("expected_revision")
            if rec["state"] in transitions.TERMINAL:
                raise RpcError("terminal", f"episode is {rec['state']}; no transition is permitted")
            if not transitions.allowed(ctx.principal, rec["state"], to) and \
                    not any(transitions.allowed(ctx.principal, f, to) for f in transitions.STATES):
                raise RpcError("forbidden_transition", f"{ctx.principal} may never set {to}")
            if expected != rec["revision"]:
                # R-7: a transition computed from a stale revision is refused; the caller re-reads.
                raise RpcError("conflict", "stale revision", {"revision": rec["revision"], "state": rec["state"]})
            if not transitions.allowed(ctx.principal, rec["state"], to):
                raise RpcError("forbidden_transition", f"{ctx.principal} may not move {rec['state']} -> {to}")
            body = {"from": rec["state"], "to": to, "reason": p.get("reason")}
            idem = p.get("idem_key") or f"state:{expected}:{to}"
            return self._append(rec, "state", body, principal=ctx.principal, session_id=None, idem_key=idem,
                                result={"revision": rec["revision"] + 1, "state": to})

    def append_signal(self, ctx: Ctx, p: dict, *, principal: str | None = None, session_id: str | None = None) -> Any:
        with self._lock:
            rec = self._record(p.get("episode_id"))
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            if rec["state"] in transitions.TERMINAL:
                raise RpcError("terminal", "episode is terminal")
            snap = p.get("snapshot") or {}
            if not _nonempty(snap.get("command_id")):
                raise RpcError("invalid", "snapshot.command_id required")
            sid = self._next_id(rec["signals"], "s")
            body = {"id": sid, "command_id": snap["command_id"], "status": snap.get("status"),
                    "summary": snap.get("structured") if snap.get("structured") is not None else snap.get("summary"),
                    "truncated": bool(snap.get("truncated")), "collected_at": snap.get("collected_at"),
                    "flags": snap.get("flags", []), "ref": snap.get("audit_ref"), "source": principal or ctx.principal}
            return self._append(rec, "signal", body, principal=principal or ctx.principal, session_id=session_id,
                                idem_key=p["idem_key"], result={"signal_id": sid})

    def _simple(self, ctx: Ctx, p: dict, kind: str, fields: tuple[str, ...]) -> Any:
        with self._lock:
            rec = self._record(p.get("episode_id"))
            prior = self._idem(rec["episode_id"], p.get("idem_key"))
            if prior is not None:
                return prior
            body = {f: p.get(f) for f in fields}
            return self._append(rec, kind, body, principal=ctx.principal, session_id=p.get("session_id"),
                                idem_key=p["idem_key"], result={"ok": True, "revision": rec["revision"] + 1})

    def append_cost(self, ctx: Ctx, p: dict) -> Any:
        if p.get("role") not in VIEW_BY_ROLE or not isinstance(p.get("usd"), (int, float)) or not isinstance(p.get("turns"), int):
            raise RpcError("invalid", "role, usd and turns required")
        return self._simple(ctx, p, "cost", ("role", "usd", "turns", "session_id", "configuration", "tokens"))

    def append_step(self, ctx: Ctx, p: dict) -> Any:
        if p.get("outcome") not in ("ok", "failed") or p.get("role") not in VIEW_BY_ROLE:
            raise RpcError("invalid", "role and outcome ok|failed required")
        return self._simple(ctx, p, "step", ("role", "session_id", "outcome", "reason", "state", "configuration"))

    def annotate(self, ctx: Ctx, p: dict) -> Any:
        if not _nonempty(p.get("note")):
            raise RpcError("invalid", "note required")
        return self._simple(ctx, p, "annotation", ("kind", "note"))

    def control_read(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            rec = self._record(p.get("episode_id"))
            view = p.get("view", "full")
            if view == "record":
                return json.loads(json.dumps(rec))
            return view_for(rec, view, self.bundles.load(rec["bundle_id"]).skills if view == "judge" else {})

    def list_episodes(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            out = []
            for rec in self._records.values():
                if p.get("nonterminal_only") and rec["state"] in transitions.TERMINAL:
                    continue
                if p.get("class") and rec["class"] != p["class"]:
                    continue
                out.append({k: rec.get(k) for k in ("episode_id", "state", "revision", "class", "bundle_id", "trigger",
                                                    "opened_at", "opened_ts", "validator_id", "consensus_mode")})
            return sorted(out, key=lambda r: r["opened_ts"] or 0)

    # --- store-verify ----------------------------------------------------------------
    def append_verification(self, ctx: Ctx, p: dict) -> Any:
        if p.get("result") not in ("pass", "fail") or not _nonempty(p.get("rule")):
            raise RpcError("invalid", "rule and result pass|fail required")
        with self._lock:
            if self._record(p.get("episode_id"))["state"] in transitions.TERMINAL:
                raise RpcError("terminal", "episode is terminal; record a recovery observation instead")
        return self._simple(ctx, p, "verification", ("rule", "result", "samples"))

    def append_recovery_observation(self, ctx: Ctx, p: dict) -> Any:
        if not _nonempty(p.get("rule")):
            raise RpcError("invalid", "rule required")
        return self._simple(ctx, p, "recovery_observation", ("rule", "note"))

    # --- store-observe ---------------------------------------------------------------
    def append_observation(self, ctx: Ctx, p: dict) -> Any:
        with self._lock:
            cap = self.tokens.check(p.get("token"), episode_id=p.get("episode_id"))
            rec = self._record(cap.episode_id)
            if cap.bundle_id != rec["bundle_id"]:
                raise RpcError("bundle_refused", "token bundle differs from the episode's bound bundle")
            return self.append_signal(ctx, p, principal=f"observer_broker/agent:{cap.role}", session_id=cap.session_id)

    # --- endpoints -------------------------------------------------------------------
    def endpoints(self, sock_dir: str, uids: dict[str, set[int]]) -> list[Endpoint]:
        """The agent endpoint is split per broker so the socket itself is the principal:
        the report broker's socket serves only append_report and read_episode."""
        agent = {
            "append_hypothesis": self.append_hypothesis,
            "append_hypothesis_status": self.append_hypothesis_status,
            "append_recommendation": self.append_recommendation,
            "append_no_action": self.append_no_action,
            "append_verdict": self.append_verdict,
            "read_episode": self.agent_read,
        }
        agent_report = {"append_report": self.append_report, "read_episode": self.agent_read}
        control = {
            "open_episode": self.open_episode, "set_state": self.set_state, "append_signal": self.append_signal,
            "append_cost": self.append_cost, "append_step": self.append_step, "annotate": self.annotate,
            "read_episode": self.control_read, "list_episodes": self.list_episodes,
        }
        verify = {
            "append_verification": self.append_verification,
            "append_recovery_observation": self.append_recovery_observation,
            "set_state": self._verifier_set_state, "read_episode": self.control_read, "list_episodes": self.list_episodes,
        }
        observe = {"append_observation": self.append_observation}
        return [
            Endpoint("store-agent", f"{sock_dir}/agent.sock", "episode_broker", uids["episode_broker"], agent),
            Endpoint("store-agent-report", f"{sock_dir}/agent-report.sock", "report_broker", uids["report_broker"], agent_report),
            Endpoint("store-control", f"{sock_dir}/control.sock", "controller", uids["controller"], control),
            Endpoint("store-verify", f"{sock_dir}/verify.sock", "verifier", uids["verifier"], verify),
            Endpoint("store-observe", f"{sock_dir}/observe.sock", "observer_broker", uids["observer_broker"], observe),
        ]

    def _verifier_set_state(self, ctx: Ctx, p: dict) -> Any:
        if p.get("state") != "resolved":
            raise RpcError("forbidden_transition", "the verifier endpoint can only set resolved")
        return self.set_state(ctx, p)
