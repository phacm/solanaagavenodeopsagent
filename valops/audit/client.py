"""Submitter-side audit client.

Deterministic components that must keep running while the sequencer is down (sentinel,
verifier, store -- HLD §9 "sentinel and verifier continue and buffer") use
``buffer=True``: entries are queued in order and flushed on the next successful call.
The LLM path never buffers: the controller's pre-flight refuses to start a step without
an audit path (RB-8).
"""
from __future__ import annotations

import base64
import collections
import logging
import threading
from typing import Any

from ..common.rpc import RpcClient, RpcError

log = logging.getLogger(__name__)


class AuditClient:
    def __init__(self, sock_path: str, *, buffer: bool = False, max_buffer: int = 10000):
        self.rpc = RpcClient(sock_path, timeout=10)
        self.buffer = buffer
        self._q: collections.deque = collections.deque(maxlen=max_buffer)
        self._lock = threading.Lock()
        self.dropped = 0

    def _params(self, event: str, episode_id: str | None, data: dict | None, payload: Any) -> dict:
        p: dict[str, Any] = {"event": event, "episode_id": episode_id, "data": data or {}}
        if isinstance(payload, (bytes, bytearray)):
            p["payload_b64"] = base64.b64encode(payload).decode()
        elif payload is not None:
            p["payload_json"] = payload
        return p

    def flush(self) -> None:
        with self._lock:
            while self._q:
                self.rpc.call("submit", **self._q[0])
                self._q.popleft()

    def submit(self, event: str, episode_id: str | None = None, data: dict | None = None, payload: Any = None) -> dict:
        params = self._params(event, episode_id, data, payload)
        try:
            self.flush()
            return self.rpc.call("submit", **params)
        except RpcError as e:
            if not self.buffer or e.code != "unavailable":
                raise
            with self._lock:
                if len(self._q) == self._q.maxlen:
                    self.dropped += 1
                self._q.append(params)
            log.warning("audit sequencer unavailable; buffered (%d queued)", len(self._q))
            return {"pending": True, "queued": len(self._q)}

    def status(self) -> dict:
        return self.rpc.call("status")

    def ref(self, result: dict) -> str:
        return f"audit:{result['seq']}" if "seq" in result else "audit:pending"
