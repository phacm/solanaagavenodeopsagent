"""Newline-delimited JSON RPC over Unix domain sockets with transport-derived principals.

D16 default: UDS with kernel peer credentials on one ops host (HLD §3, §5.3).

* The principal of a call is the *endpoint* it arrived on (one socket per principal
  class) after the kernel-reported peer uid (SO_PEERCRED) has been checked against the
  uids allowed on that endpoint. Nothing in a request can change it (SR-14, DD-8).
* Request fields that try to name the caller (``actor``, ``principal``, ``caller``) are
  stripped before dispatch and never read (HLD §2.3 item 3).
* An endpoint serves exactly the methods it was built with. Anything else fails as
  ``unknown_method`` -- the operation does not exist there (HLD §5.3). ``rpc.methods``
  returns the served list so the capability-absence suite can assert against it.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import socketserver
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

MAX_MESSAGE = 4 * 1024 * 1024
IDENTITY_FIELDS = ("actor", "principal", "caller")


class RpcError(Exception):
    def __init__(self, code: str, message: str = "", data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass(frozen=True)
class Ctx:
    endpoint: str      # e.g. "store-agent"
    principal: str     # e.g. "episode_broker" -- derived from the endpoint, never the request
    uid: int
    pid: int


Handler = Callable[[Ctx, dict], Any]


@dataclass
class Endpoint:
    name: str
    path: str
    principal: str
    allowed_uids: set[int]
    methods: dict[str, Handler]
    mode: int = 0o660

    def served(self) -> list[str]:
        return sorted(self.methods)


def peercred(sock: socket.socket) -> tuple[int, int, int]:
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    return pid, uid, gid


class _Handler(socketserver.StreamRequestHandler):
    server: "_Server"

    def handle(self) -> None:
        ep = self.server.endpoint
        try:
            pid, uid, _ = peercred(self.connection)
        except OSError:
            return
        if uid not in ep.allowed_uids:
            self._send({"id": None, "error": RpcError("denied", "peer uid not permitted on this endpoint").to_dict()})
            log.warning("endpoint %s refused uid %s pid %s", ep.name, uid, pid)
            return
        ctx = Ctx(endpoint=ep.name, principal=ep.principal, uid=uid, pid=pid)
        while True:
            line = self.rfile.readline(MAX_MESSAGE + 1)
            if not line:
                return
            if len(line) > MAX_MESSAGE:
                self._send({"id": None, "error": RpcError("too_large", "request exceeds cap").to_dict()})
                return
            self._send(self._dispatch(ctx, line))

    def _dispatch(self, ctx: Ctx, line: bytes) -> dict:
        ep = self.server.endpoint
        try:
            req = json.loads(line)
            rid = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}
            if not isinstance(params, dict):
                raise RpcError("invalid", "params must be an object")
        except (ValueError, AttributeError) as e:
            return {"id": None, "error": RpcError("invalid", f"bad request: {e}").to_dict()}
        for f in IDENTITY_FIELDS:
            params.pop(f, None)  # HLD §2.3 item 3: ignored if present
        if method == "rpc.methods":
            return {"id": rid, "result": ep.served()}
        fn = ep.methods.get(method)
        if fn is None:
            return {"id": rid, "error": RpcError("unknown_method", f"{method!r} does not exist on {ep.name}").to_dict()}
        try:
            return {"id": rid, "result": fn(ctx, params)}
        except RpcError as e:
            return {"id": rid, "error": e.to_dict()}
        except Exception as e:  # noqa: BLE001 - a handler bug must not kill the server
            log.exception("handler %s.%s failed", ep.name, method)
            return {"id": rid, "error": RpcError("internal", type(e).__name__).to_dict()}

    def _send(self, obj: dict) -> None:
        try:
            self.wfile.write(json.dumps(obj, separators=(",", ":")).encode() + b"\n")
            self.wfile.flush()
        except OSError:
            pass


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, endpoint: Endpoint):
        self.endpoint = endpoint
        p = Path(endpoint.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() or p.is_socket():
            p.unlink()
        super().__init__(str(p), _Handler)
        os.chmod(p, endpoint.mode)


class RpcServer:
    """Hosts one or more endpoints, each on its own socket and thread."""

    def __init__(self, endpoints: list[Endpoint]):
        self.endpoints = endpoints
        self._servers: list[_Server] = []
        self._threads: list[threading.Thread] = []

    def start(self) -> "RpcServer":
        for ep in self.endpoints:
            srv = _Server(ep)
            t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, name=f"rpc-{ep.name}", daemon=True)
            t.start()
            self._servers.append(srv)
            self._threads.append(t)
        return self

    def stop(self) -> None:
        for srv in self._servers:
            srv.shutdown()
            srv.server_close()
            try:
                Path(srv.endpoint.path).unlink()
            except FileNotFoundError:
                pass
        self._servers.clear()


class RpcClient:
    def __init__(self, path: str, timeout: float = 30.0):
        self.path = path
        self.timeout = timeout
        self._n = 0
        self._lock = threading.Lock()

    def call(self, method: str, **params: Any) -> Any:
        with self._lock:
            self._n += 1
            rid = self._n
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            try:
                s.connect(self.path)
            except OSError as e:
                raise RpcError("unavailable", f"{self.path}: {e}") from e
            s.sendall(json.dumps({"id": rid, "method": method, "params": params}, separators=(",", ":")).encode() + b"\n")
            f = s.makefile("rb")
            line = f.readline(MAX_MESSAGE + 1)
        if not line:
            raise RpcError("unavailable", "connection closed without response")
        resp = json.loads(line)
        if "error" in resp:
            e = resp["error"]
            raise RpcError(e.get("code", "error"), e.get("message", ""), e.get("data"))
        return resp.get("result")

    def methods(self) -> list[str]:
        return self.call("rpc.methods")
