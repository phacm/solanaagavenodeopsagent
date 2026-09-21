"""episode-broker [3] (HLD §4.1, §7.5). Worker-facing; forwards typed T1 writes and
episode reads to the store's agent endpoint. It holds no transition, verification or
closure operation because the endpoint it talks to has none (DD-8)."""
from __future__ import annotations

import re
from typing import Any

from ..bundle.registry import BundleRegistry
from ..common.rpc import Ctx, Endpoint, RpcClient, RpcError
from ..common.tokens import TokenGate
from .base import BrokerBase

WRITE_QUOTA_FACTOR = 4  # per-session write cap = 4 x P-05[role]


class EpisodeBroker(BrokerBase):
    name = "episode_broker"

    def __init__(self, gate: TokenGate, audit, store_agent_sock: str, bundles: BundleRegistry):
        super().__init__(gate, audit)
        self.store = RpcClient(store_agent_sock)
        self.bundles = bundles

    def _write(self, p: dict, tool: str, op: str, build) -> Any:
        cap, args = self.authorize(p, tool)
        limit = WRITE_QUOTA_FACTOR * int(self.bundles.load(cap.bundle_id).param("P-05", cap.role))
        self.quota.take((cap.session_id, "writes"), limit)
        idem = p.get("idem_key")
        if not isinstance(idem, str) or not re.fullmatch(r"[A-Za-z0-9:_\-]{8,120}", idem):
            raise RpcError("invalid", "idem_key required")
        self._audit("tool_call", cap, {"tool": tool}, payload=args)
        try:
            res = self.store.call(op, token=p["token"], episode_id=cap.episode_id, idem_key=f"{cap.session_id}:{idem}",
                                  **build(args))
        except RpcError as e:
            self._audit("tool_denied", cap, {"tool": tool, "reason": e.code, "message": e.message[:300]})
            raise
        self._audit("tool_result", cap, {"tool": tool}, payload=res)
        return res

    def add_hypothesis(self, ctx: Ctx, p: dict) -> Any:
        return self._write(p, "add_hypothesis", "append_hypothesis", lambda a: {"hypothesis": a})

    def set_hypothesis_status(self, ctx: Ctx, p: dict) -> Any:
        return self._write(p, "set_hypothesis_status", "append_hypothesis_status", lambda a: a)

    def propose_recommendation(self, ctx: Ctx, p: dict) -> Any:
        return self._write(p, "propose_recommendation", "append_recommendation", lambda a: {"recommendation": a})

    def report_no_action(self, ctx: Ctx, p: dict) -> Any:
        return self._write(p, "report_no_action", "append_no_action", lambda a: a)

    def submit_verdict(self, ctx: Ctx, p: dict) -> Any:
        return self._write(p, "submit_verdict", "append_verdict", lambda a: a)

    def read_episode(self, ctx: Ctx, p: dict) -> Any:
        cap = self.gate.check(p.get("token"), episode_id=p.get("episode_id"))
        self.quota.take((cap.session_id, "reads"), 4 * int(self.bundles.load(cap.bundle_id).param("P-05", cap.role)))
        return self.store.call("read_episode", token=p["token"], episode_id=cap.episode_id)

    def get_verification_result(self, ctx: Ctx, p: dict) -> Any:
        cap, _ = self.authorize(p, "get_verification_result")
        view = self.store.call("read_episode", token=p["token"], episode_id=cap.episode_id)
        return {"verifications": view.get("verifications", []), "recovery_observations": view.get("recovery_observations", []),
                "state": view.get("state")}

    def draft_failover_runbook(self, ctx: Ctx, p: dict) -> Any:
        cap, _ = self.authorize(p, "draft_failover_runbook")
        view = self.store.call("read_episode", token=p["token"], episode_id=cap.episode_id)
        mode = view.get("consensus_mode")
        if mode not in ("tower", "alpenglow"):
            raise RpcError("mode_unknown", "consensus mode is unknown: the failover checklist is mode-specific and is withheld")
        bundle = self.bundles.load(cap.bundle_id)
        f = bundle.skill_file("failover-runbook-draft")
        if not f.exists():
            raise RpcError("not_found", "bundle has no failover-runbook-draft skill")
        text = f.read_text()
        section = _section(text, mode) or text
        self._audit("tool_call", cap, {"tool": "draft_failover_runbook", "mode": mode})
        return {"mode": mode, "checklist": section, "note": "Text only. Nothing is executed by this system."}

    def audit_note(self, ctx: Ctx, p: dict) -> Any:
        """First-line audit records from the worker's hooks (defence in depth, §6.3). The
        actor is stamped by the sequencer; role/session come from the verified token."""
        cap = self.gate.check(p.get("token"), episode_id=p.get("episode_id"))
        self.quota.take((cap.session_id, "notes"), 500)
        data = p.get("data") if isinstance(p.get("data"), dict) else {}
        return {"ref": self._audit("hook", cap, {"hook": str(p.get("hook", ""))[:40], **{k: str(v)[:500] for k, v in data.items()}})}

    def endpoints(self, sock_dir: str, worker_uids: set[int], controller_uids: set[int]) -> list[Endpoint]:
        methods = {n: getattr(self, n) for n in (
            "add_hypothesis", "set_hypothesis_status", "propose_recommendation", "report_no_action", "submit_verdict",
            "read_episode", "get_verification_result", "draft_failover_runbook", "audit_note")}
        return [Endpoint("episode-broker", f"{sock_dir}/worker.sock", "worker", worker_uids, methods),
                self.admin_endpoint(f"{sock_dir}/admin.sock", controller_uids)]


def _section(text: str, mode: str) -> str | None:
    m = re.search(rf"(?ims)^##\s+.*\b{mode}\b.*?$(.*?)(?=^##\s|\Z)", text)
    return m.group(0).strip() if m else None
