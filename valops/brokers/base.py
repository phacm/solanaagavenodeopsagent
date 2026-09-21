"""Shared broker machinery: the broker-side re-enforcement of every hook check (HLD §6.3).

    1. tool is in this role's allowlist          -> ``authorize``
    2. arguments conform to the tool schema       -> ``authorize``
    3. rate and quota limits for role/episode     -> ``Quota``
    4. episode state makes the tool legal         -> enforced by the store for writes; for
                                                     reads the role in the token implies it
    5. bound bundle still verifies                -> TokenGate(bundle_ok=registry.verify)

The principal is the authenticated socket plus the capability token -- never anything
the worker asserts (§4.3).
"""
from __future__ import annotations

import threading
from typing import Any

from ..audit.client import AuditClient
from ..common.rpc import Ctx, Endpoint, RpcError
from ..common.schema import SchemaError, validate
from ..common.tokens import Capability, TokenGate
from ..common.tools import TOOLS_BY_NAME, tool_allowed


class Quota:
    def __init__(self) -> None:
        self._n: dict[tuple, int] = {}
        self._lock = threading.Lock()

    def take(self, key: tuple, limit: int) -> None:
        with self._lock:
            n = self._n.get(key, 0)
            if n >= limit:
                raise RpcError("quota", f"limit {limit} reached for {key[-1]}")
            self._n[key] = n + 1


class BrokerBase:
    name = "broker"

    def __init__(self, gate: TokenGate, audit: AuditClient | None):
        self.gate = gate
        self.audit = audit
        self.quota = Quota()

    def authorize(self, p: dict, tool: str) -> tuple[Capability, dict]:
        cap = self.gate.check(p.get("token"), episode_id=p.get("episode_id"))
        if not tool_allowed(cap.role, tool):
            self._audit("tool_denied", cap, {"tool": tool, "reason": "role"})
            raise RpcError("forbidden", f"role {cap.role} may not call {tool}")
        args = p.get("args") or {}
        try:
            validate(args, TOOLS_BY_NAME[tool].input_schema)
        except SchemaError as e:
            self._audit("tool_denied", cap, {"tool": tool, "reason": f"schema: {e}"})
            raise RpcError("invalid_args", str(e)) from e
        return cap, args

    def _audit(self, event: str, cap: Capability | None, data: dict, payload: Any = None) -> str:
        if self.audit is None:
            return "audit:none"
        d = dict(data)
        if cap is not None:
            d.update({"worker_role": cap.role, "session_id": cap.session_id, "bundle_id": cap.bundle_id})
        r = self.audit.submit(event, cap.episode_id if cap else None, d, payload)
        return self.audit.ref(r)

    def admin_endpoint(self, path: str, controller_uids: set[int], extra: dict | None = None) -> Endpoint:
        def revoke(ctx: Ctx, p: dict) -> dict:
            sid = p.get("session_id")
            if not isinstance(sid, str) or not sid:
                raise RpcError("invalid", "session_id required")
            self.gate.revoke_session(sid)
            return {"revoked": sid}

        methods = {"revoke_session": revoke, "ping": lambda ctx, p: {"ok": True, "broker": self.name}}
        methods.update(extra or {})
        return Endpoint(f"{self.name}-admin", path, "controller", controller_uids, methods)
