"""Capability tokens (HLD §4.2, §5.2 R-10, SR-14).

A token is scoped to (episode, role, session, bundle, expiry, nonce). It is minted by the
controller with its Ed25519 key and verified by every broker and by the store with the
public key. Revocation at step end is per session and is pushed by the controller to
every broker's admin endpoint; bundle revocation is read from the bundle registry.
"""
from __future__ import annotations

import json
import secrets
import threading
from dataclasses import asdict, dataclass

from .canonical import b64u, b64u_dec, canonical, now
from .crypto import Signer, Verifier
from .rpc import RpcError

ROLES = ("diagnostician", "change_planner", "proposal_judge", "reporter")


@dataclass(frozen=True)
class Capability:
    episode_id: str
    role: str
    session_id: str
    bundle_id: str
    exp: float
    nonce: str
    iat: float
    v: int = 1


def mint(signer: Signer, *, episode_id: str, role: str, session_id: str, bundle_id: str, ttl_s: float) -> str:
    if role not in ROLES:
        raise ValueError(f"unknown role {role}")
    t = now()
    cap = Capability(episode_id, role, session_id, bundle_id, exp=t + ttl_s, nonce=secrets.token_hex(12), iat=t)
    body = canonical(asdict(cap))
    return b64u(body) + "." + b64u(signer.sign(body))


class TokenGate:
    """Verification used by brokers and the store. ``bundle_ok`` is a callable that
    re-verifies the bound bundle (integrity + not revoked) on every call (HLD §5.4)."""

    def __init__(self, verifier: Verifier, bundle_ok=None):
        self._verifier = verifier
        self._bundle_ok = bundle_ok
        self._revoked: set[str] = set()
        self._lock = threading.Lock()

    def revoke_session(self, session_id: str) -> None:
        with self._lock:
            self._revoked.add(session_id)

    def check(self, token: str | None, *, episode_id: str | None = None, role: str | None = None) -> Capability:
        if not token or not isinstance(token, str) or token.count(".") != 1:
            raise RpcError("unauthenticated", "capability token missing or malformed")
        body_s, sig_s = token.split(".")
        try:
            body, sig = b64u_dec(body_s), b64u_dec(sig_s)
        except ValueError as e:
            raise RpcError("unauthenticated", "token encoding") from e
        if not self._verifier.verify(sig, body):
            raise RpcError("unauthenticated", "token signature invalid")
        try:
            cap = Capability(**json.loads(body))
        except (TypeError, ValueError) as e:
            raise RpcError("unauthenticated", "token body") from e
        if cap.exp < now():
            raise RpcError("token_expired", "capability token expired")
        with self._lock:
            if cap.session_id in self._revoked:
                raise RpcError("token_revoked", "session ended")
        if episode_id is not None and episode_id != cap.episode_id:
            raise RpcError("forbidden", "token is bound to a different episode")
        if role is not None and role != cap.role:
            raise RpcError("forbidden", "token is bound to a different role")
        if self._bundle_ok is not None:
            reason = self._bundle_ok(cap.bundle_id)
            if reason:
                raise RpcError("bundle_refused", reason)
        return cap
