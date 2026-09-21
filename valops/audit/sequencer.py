"""Audit sequencer [5] (HLD §5.5, SR-13, SR-15, DD-9).

ONE process writes the ops-host chain. Every other component submits over its own
socket; the sequencer assigns ``seq``, links ``prev``, stamps ``actor`` from the
authenticated endpoint (a submitted actor is ignored), hashes and stores payloads by
reference, fsyncs before acknowledging, and every P-18 signs {chain_head, seq, ts} and
writes it to the external anchor store. It also records the observer daemon's signed
checkpoints so truncation or rewrite of the validator-host chain is detectable here.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from ..common.canonical import b64u, b64u_dec, canonical, now, sha256_hex
from ..common.crypto import Signer, Verifier
from ..common.rpc import Endpoint, RpcError
from .anchor import AnchorStore

log = logging.getLogger(__name__)

GENESIS = "0" * 64
EVENTS = {
    "tool_call", "tool_result", "tool_denied", "state_change", "integrity_fail", "alert", "observe_request",
    "observe_result", "observe_checkpoint", "verification", "anchor", "store_write", "model_request",
    "model_refusal", "token_minted", "token_revoked", "step", "bundle", "hook", "sentinel",
}
MAX_PAYLOAD = 8 * 1024 * 1024


def entry_hash(entry: dict) -> str:
    return sha256_hex(canonical(entry))


def anchor_body(a: dict) -> bytes:
    return canonical({k: a[k] for k in ("chain_head", "seq", "ts_ms", "key_id")})


class AuditSequencer:
    def __init__(self, chain_path: str | os.PathLike, payload_dir: str | os.PathLike, signer: Signer, key_id: str,
                 anchor_store: AnchorStore, anchor_interval_s: float, daemon_verifier: Verifier | None = None):
        self.chain_path = Path(chain_path)
        self.payload_dir = Path(payload_dir)
        self.signer, self.key_id = signer, key_id
        self.anchors = anchor_store
        self.anchor_interval_s = anchor_interval_s
        self.daemon_verifier = daemon_verifier
        self._lock = threading.Lock()
        self.seq = 0
        self.head = GENESIS
        self.last_anchor_ts: float | None = None
        self.daemon_last: dict | None = None
        self.integrity_error: str | None = None
        self._stop = threading.Event()
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        self._fh = open(self.chain_path, "ab")

    def _load(self) -> None:
        if not self.chain_path.exists():
            return
        prev = GENESIS
        with open(self.chain_path, "rb") as f:
            for n, line in enumerate(f, 1):
                e = json.loads(line)
                if e["prev"] != prev or e["seq"] != n:
                    self.integrity_error = f"chain broken at line {n}"
                    log.error(self.integrity_error)
                prev = entry_hash(e)
                self.seq = e["seq"]
                if e["event"] == "anchor":
                    self.last_anchor_ts = e["ts"]
                if e["event"] == "observe_checkpoint" and e["data"].get("accepted"):
                    self.daemon_last = {"seq": e["data"]["seq"], "head": e["data"]["head"]}
        self.head = prev

    # --- writing ---------------------------------------------------------------------
    def _append(self, actor: str, event: str, episode_id: str | None, data: dict, payload_ref: str | None) -> dict:
        with self._lock:
            entry = {
                "seq": self.seq + 1, "ts": now(), "prev": self.head, "actor": actor, "event": event,
                "episode_id": episode_id, "data": data, "payload_ref": payload_ref,
            }
            self._fh.write(canonical(entry) + b"\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())  # durability: fsync before acknowledgement
            self.seq += 1
            self.head = entry_hash(entry)
            return {"seq": entry["seq"], "hash": self.head, "payload_ref": payload_ref}

    def _store_payload(self, raw: bytes) -> str:
        if len(raw) > MAX_PAYLOAD:
            raise RpcError("too_large", "payload exceeds cap")
        h = sha256_hex(raw)
        p = self.payload_dir / h
        if not p.exists():
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, p)
        return "sha256:" + h

    def submit(self, actor: str, params: dict) -> dict:
        event = params.get("event")
        if event not in EVENTS:
            raise RpcError("invalid", f"unknown event {event!r}")
        data = params.get("data") or {}
        if not isinstance(data, dict):
            raise RpcError("invalid", "data must be an object")
        ref = None
        if params.get("payload_b64") is not None:
            ref = self._store_payload(base64.b64decode(params["payload_b64"]))
        elif params.get("payload_json") is not None:
            ref = self._store_payload(canonical(params["payload_json"]))
        return self._append(actor, event, params.get("episode_id"), data, ref)

    # --- anchoring -------------------------------------------------------------------
    def anchor_now(self) -> dict:
        with self._lock:
            seq, head = self.seq, self.head
        a = {"chain_head": head, "seq": seq, "ts_ms": int(now() * 1000), "key_id": self.key_id}
        a["sig"] = b64u(self.signer.sign(anchor_body(a)))
        self.anchors.put(a)  # raises if the anchor store is unreachable; lag then grows
        self.last_anchor_ts = now()
        self._append("audit_sequencer", "anchor", None, {"anchored_seq": seq, "chain_head": head}, None)
        return a

    def anchor_loop(self) -> None:
        while not self._stop.wait(self.anchor_interval_s):
            try:
                self.anchor_now()
            except Exception as e:  # noqa: BLE001
                log.error("anchor failed: %s", e)

    def anchor_lag_s(self) -> float | None:
        return None if self.last_anchor_ts is None else now() - self.last_anchor_ts

    def status(self) -> dict:
        return {"seq": self.seq, "head": self.head, "last_anchor_ts": self.last_anchor_ts,
                "anchor_lag_s": self.anchor_lag_s(), "integrity_error": self.integrity_error,
                "daemon_last": self.daemon_last}

    # --- validator-host chain --------------------------------------------------------
    def record_daemon_checkpoint(self, actor: str, ckpt: dict) -> dict:
        """ckpt = {seq, head, ts, since_seq, since_head, sig}; signed by the daemon key.
        since_* is the daemon's own hash at the last seq we recorded; a mismatch or a
        lower seq means the daemon chain was truncated or rewritten."""
        if self.daemon_verifier is None:
            raise RpcError("unavailable", "no daemon key configured")
        body = canonical({k: ckpt.get(k) for k in ("seq", "head", "ts", "since_seq", "since_head")})
        if not self.daemon_verifier.verify(b64u_dec(ckpt.get("sig", "")), body):
            self._append(actor, "integrity_fail", None, {"what": "daemon checkpoint signature invalid"}, None)
            raise RpcError("integrity", "daemon checkpoint signature invalid")
        problem = None
        last = self.daemon_last
        if last is not None:
            if ckpt["seq"] < last["seq"]:
                problem = f"daemon chain truncated: seq {ckpt['seq']} < recorded {last['seq']}"
            elif ckpt.get("since_seq") != last["seq"] or ckpt.get("since_head") != last["head"]:
                problem = "daemon chain rewritten: hash at last recorded seq differs"
        data = {"seq": ckpt["seq"], "head": ckpt["head"], "accepted": problem is None}
        if problem:
            data["problem"] = problem
            self._append(actor, "integrity_fail", None, {"what": problem}, None)
            self._append(actor, "observe_checkpoint", None, data, None)
            raise RpcError("integrity", problem)
        self.daemon_last = {"seq": ckpt["seq"], "head": ckpt["head"]}
        return self._append(actor, "observe_checkpoint", None, data, None)

    def stop(self) -> None:
        self._stop.set()
        self._fh.close()

    # --- endpoints -------------------------------------------------------------------
    def endpoints(self, sock_dir: str, principals: dict[str, set[int]]) -> list[Endpoint]:
        """One socket per submitting principal class; the socket IS the principal."""
        eps = []
        for principal, uids in principals.items():
            methods: dict[str, Any] = {
                "submit": lambda ctx, p: self.submit(ctx.principal, p),
                "status": lambda ctx, p: self.status(),
            }
            if principal == "observer_broker":
                methods["record_daemon_checkpoint"] = lambda ctx, p: self.record_daemon_checkpoint(ctx.principal, p)
            if principal == "controller":
                methods["anchor_now"] = lambda ctx, p: self.anchor_now()
            eps.append(Endpoint(f"audit-{principal}", f"{sock_dir}/{principal}.sock", principal, uids, methods))
        return eps


def verify_chain(chain_path: str | os.PathLike, anchors: list[dict], anchor_keys: dict[str, Verifier]) -> dict:
    """Walk every link and compare the chain with every anchor (HLD §5.5 Verification).
    A local rewrite shows up as an anchored (seq, head) the local chain no longer has."""
    errors: list[str] = []
    hashes: dict[int, str] = {}
    prev, seq = GENESIS, 0
    p = Path(chain_path)
    if p.exists():
        with open(p, "rb") as f:
            for n, line in enumerate(f, 1):
                try:
                    e = json.loads(line)
                except ValueError:
                    errors.append(f"line {n}: unparseable")
                    break
                if e.get("seq") != n:
                    errors.append(f"line {n}: seq {e.get('seq')} != {n}")
                if e.get("prev") != prev:
                    errors.append(f"seq {n}: prev link broken")
                prev = entry_hash(e)
                hashes[n] = prev
                seq = n
    newest = None
    for a in sorted(anchors, key=lambda a: a["seq"]):
        key = anchor_keys.get(a.get("key_id", ""))
        if key is None or not key.verify(b64u_dec(a["sig"]), anchor_body(a)):
            errors.append(f"anchor at seq {a['seq']}: signature invalid")
            continue
        if a["seq"] == 0:
            continue
        if a["seq"] > seq:
            errors.append(f"anchor at seq {a['seq']} beyond local chain end {seq} (truncation)")
        elif hashes.get(a["seq"]) != a["chain_head"]:
            errors.append(f"anchor at seq {a['seq']}: local chain differs from anchored head (rewrite)")
        newest = a
    return {"ok": not errors, "entries": seq, "head": prev, "errors": errors,
            "newest_anchor_seq": newest["seq"] if newest else None}
