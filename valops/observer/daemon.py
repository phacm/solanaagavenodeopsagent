"""Observer Daemon [9] -- validator host, user `valops`, non-root, no keys (HLD §5.11).

    POST /observe   {command_id, args, request_id}
                    -> {status, structured, output, truncated, collected_at, audit_ref, flags}
    GET  /checkpoint?since=<seq>   signed local-chain checkpoint (OD-10)
    GET  /health

OD-1 unknown id rejected before any spawn · OD-2 typed args, argv without a shell ·
OD-3 table loader refuses non-read-only entries · OD-4 capped, structured, redacted,
flagged · OD-5 per-command rate limit and concurrency of one · OD-7 timeout is a
reported outcome, never a retry · OD-9 local-RPC circuit breaker · OD-10 local chain.
OD-6 / OD-8 are enforced by the systemd unit (deploy/validator-host/valops-observerd.service).
"""
from __future__ import annotations

import collections
import json
import logging
import os
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..common.canonical import now, sha256_hex
from .builtins import BUILTINS
from .chain import LocalChain
from .parsers import PARSERS
from .redact import cap, redact, suspicious
from .table import Command, CommandTable
from .validate import ArgError, assemble_argv, validate_args

log = logging.getLogger(__name__)
MAX_BODY = 16384
SAFE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/nonexistent", "NO_COLOR": "1"}


class Breaker:
    """OD-9: trips when local RPC latency exceeds the threshold (P-16) or RPC is unhealthy;
    closes after `recover_samples` consecutive good samples. Trips are reported, never silent."""

    def __init__(self, threshold_ms: float, recover_samples: int):
        self.threshold_ms = threshold_ms
        self.recover = recover_samples
        self.open = False
        self.good = 0
        self.trips = 0
        self.opened_at: float | None = None

    def sample(self, latency_ms: float, healthy: bool) -> None:
        bad = (not healthy) or latency_ms > self.threshold_ms
        if bad:
            if not self.open:
                self.open, self.opened_at = True, now()
                self.trips += 1
            self.good = 0
        elif self.open:
            self.good += 1
            if self.good >= self.recover:
                self.open, self.opened_at = False, None

    def state(self) -> dict:
        return {"open": self.open, "trips": self.trips, "opened_at": self.opened_at, "threshold_ms": self.threshold_ms}


class ObserverDaemon:
    def __init__(self, table: CommandTable, local: dict, chain: LocalChain, *, rate_per_min: int,
                 breaker_threshold_ms: float, breaker_recover_samples: int = 5):
        self.table = table
        self.local = local
        self.chain = chain
        self.rate = rate_per_min
        self.breaker = Breaker(breaker_threshold_ms, breaker_recover_samples)
        self._locks = {cid: threading.Lock() for cid in table.commands}
        self._calls: dict[str, collections.deque] = {cid: collections.deque() for cid in table.commands}
        self._rl = threading.Lock()

    def _rate_ok(self, cid: str) -> bool:
        with self._rl:
            q, t = self._calls[cid], time.monotonic()
            while q and t - q[0] > 60:
                q.popleft()
            if len(q) >= self.rate:
                return False
            q.append(t)
            return True

    def _exec(self, cmd: Command, argv: list[str]) -> tuple[str, bytes, bool]:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env=SAFE_ENV, start_new_session=True, shell=False)
        buf = bytearray()
        over = [False]

        def reader() -> None:
            assert proc.stdout is not None
            for chunk in iter(lambda: proc.stdout.read(4096), b""):
                if len(buf) < cmd.output_cap_bytes:
                    buf.extend(chunk)
                else:
                    over[0] = True  # keep draining so the child never blocks; discard

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        try:
            rc = proc.wait(timeout=cmd.timeout_s)
            status = "ok" if rc == 0 else "error"
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
            proc.wait()
            status = "ok" if cmd.timeout_is_sample else "timeout"
        t.join(timeout=2)
        data, truncated = cap(bytes(buf), cmd.output_cap_bytes)
        return status, data, truncated or over[0]

    def observe(self, command_id: Any, args: Any, request_id: Any) -> dict:
        t0 = time.monotonic()
        base = {"command_id": command_id, "request_id": request_id, "collected_at": now()}
        cmd = self.table.commands.get(command_id) if isinstance(command_id, str) else None
        if cmd is None:
            return self._finish(base, "rejected", {"error": "unknown command_id"}, "", False, t0)  # OD-1
        try:
            vargs = validate_args(cmd, args)
        except ArgError as e:
            return self._finish(base, "rejected", {"error": str(e)}, "", False, t0)
        if cmd.kind == "unavailable":
            return self._finish(base, "unavailable", {"reason": "query not verified against a primary source [U]"}, "", False, t0)
        if cmd.rpc_backed and self.breaker.open:
            return self._finish(base, "suspended", {"breaker": self.breaker.state()}, "", False, t0)
        if not self._rate_ok(cmd.id):
            return self._finish(base, "rate_limited", {}, "", False, t0)
        lock = self._locks[cmd.id]
        if not lock.acquire(blocking=False):  # concurrency of one (OD-5)
            return self._finish(base, "busy", {}, "", False, t0)
        try:
            if cmd.kind == "builtin":
                try:
                    text, structured = BUILTINS[cmd.id](vargs, self.local)
                    status, truncated = "ok", False
                    raw, truncated = cap(text.encode(), cmd.output_cap_bytes)
                    text = raw.decode(errors="replace")
                except OSError as e:
                    return self._finish(base, "error", {"error": type(e).__name__}, "", False, t0)
                if cmd.id == "rpc_latency":
                    self.breaker.sample(structured["latency_ms"], structured["healthy"])
                    structured = {**structured, "breaker": self.breaker.state()}
            else:
                argv = assemble_argv(cmd, vargs, self.local)
                try:
                    status, raw, truncated = self._exec(cmd, argv)
                except OSError as e:
                    return self._finish(base, "error", {"error": type(e).__name__}, "", False, t0)
                text = raw.decode(errors="replace")
                parser = PARSERS.get(cmd.parser or "")
                structured = parser(text, self.local) if parser and status == "ok" else {"parsed": False}
        finally:
            lock.release()
        return self._finish(base, status, structured, text, truncated, t0)

    def _finish(self, base: dict, status: str, structured: dict, text: str, truncated: bool, t0: float) -> dict:
        flags = suspicious(text)
        text, n_redacted = redact(text)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        ref = self.chain.append({"request_id": base["request_id"], "command_id": base["command_id"], "status": status,
                                 "output_hash": sha256_hex(text.encode()), "elapsed_ms": elapsed})
        return {**base, "status": status, "structured": structured, "output": text, "truncated": truncated,
                "flags": flags, "redactions": n_redacted, "elapsed_ms": elapsed, "audit_ref": f"daemon:{ref['seq']}"}


def make_handler(daemon: ObserverDaemon, expected_client_cn: str | None):
    class H(BaseHTTPRequestHandler):
        server_version = "valops-observerd"
        sys_version = ""

        def log_message(self, fmt: str, *args: Any) -> None:
            log.info("%s " + fmt, self.client_address[0], *args)

        def _client_ok(self) -> bool:
            if expected_client_cn is None:
                return True
            cert = self.connection.getpeercert() if hasattr(self.connection, "getpeercert") else None
            cns = [v for rdn in (cert or {}).get("subject", ()) for k, v in rdn if k == "commonName"]
            return expected_client_cn in cns

        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if not self._client_ok():
                return self._send(403, {"error": "client identity"})
            if urlparse(self.path).path != "/observe":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": "body size"})
            try:
                req = json.loads(self.rfile.read(n))
            except ValueError:
                return self._send(400, {"error": "json"})
            if not isinstance(req, dict):
                return self._send(400, {"error": "json object required"})
            self._send(200, daemon.observe(req.get("command_id"), req.get("args"), req.get("request_id")))

        def do_GET(self) -> None:  # noqa: N802
            if not self._client_ok():
                return self._send(403, {"error": "client identity"})
            u = urlparse(self.path)
            if u.path == "/checkpoint":
                q = parse_qs(u.query)
                since = int(q["since"][0]) if "since" in q and q["since"][0].isdigit() else None
                return self._send(200, daemon.chain.checkpoint(since))
            if u.path == "/health":
                return self._send(200, {"ok": True, "breaker": daemon.breaker.state(), "chain_seq": daemon.chain.seq})
            self._send(404, {"error": "not found"})

    return H


def serve(daemon: ObserverDaemon, host: str, port: int, *, certfile: str | None, keyfile: str | None,
          client_ca: str | None, expected_client_cn: str | None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(daemon, expected_client_cn))
    if certfile:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.load_cert_chain(certfile, keyfile)
        ctx.verify_mode = ssl.CERT_REQUIRED  # mTLS: the observer broker must present a client cert
        ctx.load_verify_locations(client_ca)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return httpd
