"""Model broker [12] (HLD §5.12, plan §5.12.2, DD-13). SOLE holder of provider keys and
the worker's ONLY egress.

Per worker, the controller asks for a session; the broker creates one UDS for it (MB-1)
speaking provider-native HTTP. Inside the sandbox a loopback bridge forwards
127.0.0.1:<port> to that socket. Per request:

  1 principal  = the socket the request arrived on -> (episode, role, session, configuration)
  2 route      : /<provider>/... must equal the configuration's provider
  3 model      : must equal the configuration's pinned model
  4 limits     : requests, input tokens, output tokens (clamped so the cap cuts exactly), USD
  5 strip      : every inbound credential header removed; only allowlisted headers forwarded
  6 inject     : the provider key from broker-only storage
  7 forward    : TLS to the endpoint fixed in the bundle's providers.yaml; nothing else
  8 meter      : usage from the response -> per-session counters -> controller cost record
  9 audit      : request/response hashed and stored by reference via the sequencer
 10 return     : provider response, or a provider-shaped error on refusal

MB-2 refusals are step failures, never retried here. MB-5 a provider without a D21
approval on record (broker-side file, not the bundle) is unroutable.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import socketserver
import ssl
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..bundle.registry import BundleRegistry
from ..common.canonical import now, sha256_hex
from ..common.rpc import Ctx, Endpoint, RpcError, peercred
from . import providers as pv

log = logging.getLogger(__name__)
MAX_REQUEST = 4 * 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
AUDIT_CAP = 1024 * 1024


@dataclass
class Session:
    session_id: str
    episode_id: str
    role: str
    bundle_id: str
    configuration: str
    provider: str
    model: str
    upstream: str
    price_in: float    # USD per token
    price_out: float
    max_requests: int
    max_input_tokens: int
    max_output_tokens: int
    max_usd: float
    socket_path: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    refusals: list[dict] = field(default_factory=list)
    upstream_errors: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def meter(self) -> dict:
        return {"session_id": self.session_id, "configuration": self.configuration, "provider": self.provider,
                "model": self.model, "requests": self.requests, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "usd": round(self.usd, 6), "refusals": list(self.refusals),
                "upstream_errors": self.upstream_errors,
                "limits": {"requests": self.max_requests, "input_tokens": self.max_input_tokens,
                           "output_tokens": self.max_output_tokens, "usd": self.max_usd}}


class Refusal(Exception):
    def __init__(self, status: int, cause: str, message: str):
        super().__init__(message)
        self.status, self.cause, self.message = status, cause, message


class _UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, handler, session: Session, broker: "ModelBroker", worker_uids: set[int]):
        self.session, self.broker, self.worker_uids = session, broker, worker_uids
        super().__init__(path, handler)

    def verify_request(self, request, client_address) -> bool:  # type: ignore[override]
        try:
            _, uid, _ = peercred(request)
        except OSError:
            return False
        return uid in self.worker_uids


class _Handler(BaseHTTPRequestHandler):
    server: _UnixHTTPServer
    protocol_version = "HTTP/1.1"

    def address_string(self) -> str:
        return "worker"

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("model-broker %s: " + fmt, self.server.session.session_id, *args)

    def do_GET(self) -> None:  # noqa: N802
        self._refuse(pv.error_body(self.server.session.provider, 403, "method not permitted"), 403)

    def do_POST(self) -> None:  # noqa: N802
        self.server.broker.handle(self)

    def _refuse(self, body: bytes, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ModelBroker:
    name = "model_broker"

    def __init__(self, sessions_dir: str | Path, bundles: BundleRegistry, keys: dict[str, str], approved_providers: set[str],
                 audit, worker_uids: set[int], *, allow_insecure_upstream: bool = False, development: bool = False):
        self.dir = Path(sessions_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.bundles = bundles
        self._keys = keys
        self.approved = approved_providers
        self.audit = audit
        self.worker_uids = worker_uids
        self.allow_insecure = allow_insecure_upstream
        self.development = development
        self.sessions: dict[str, Session] = {}
        self._servers: dict[str, _UnixHTTPServer] = {}
        self._closed: dict[str, dict] = {}
        self._lock = threading.Lock()

    # --- admin (controller) ----------------------------------------------------------
    def open_session(self, ctx: Ctx, p: dict) -> dict:
        sid, eid, role, bundle_id = p.get("session_id"), p.get("episode_id"), p.get("role"), p.get("bundle_id")
        if not all(isinstance(x, str) and x for x in (sid, eid, role, bundle_id)):
            raise RpcError("invalid", "session_id, episode_id, role, bundle_id required")
        bundle = self.bundles.load(bundle_id)  # binding comes from the bundle, not from the caller
        conf_name, conf = bundle.configuration_for(role)
        provider = conf["provider"]
        if provider not in self.approved:
            raise RpcError("provider_unapproved", f"{provider} has no D21 data-handling approval on record (MB-5)")
        if conf.get("admission") not in ("admitted", "native_only") and not self.development:
            raise RpcError("not_admitted", f"configuration {conf_name} has not passed PA")
        if provider not in self._keys:
            raise RpcError("no_key", f"no key for {provider}")
        upstream = (bundle.providers.get("endpoints") or {}).get(provider)
        if not upstream or (not upstream.startswith("https://") and not self.allow_insecure):
            raise RpcError("invalid", f"bundle endpoint for {provider} must be https")
        price = bundle.pricing[provider][conf["model"]]
        lim = bundle.param("P-30", configuration=conf_name)
        path = str(self.dir / f"{sid}.sock")
        s = Session(sid, eid, role, bundle_id, conf_name, provider, conf["model"], upstream,
                    price["input_per_mtok"] / 1e6, price["output_per_mtok"] / 1e6,
                    max_requests=int(bundle.param("P-05", role, conf_name)),  # P-30 requests = P-05
                    max_input_tokens=int(lim["input_tokens"][role]), max_output_tokens=int(lim["output_tokens"][role]),
                    max_usd=float(bundle.param("P-06", role, conf_name)), socket_path=path)
        with self._lock:
            if sid in self.sessions or sid in self._closed:
                raise RpcError("conflict", "session id reused")
            if os.path.exists(path):
                os.unlink(path)
            srv = _UnixHTTPServer(path, _Handler, s, self, self.worker_uids)
            os.chmod(path, 0o660)
            threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, name=f"mb-{sid[:8]}", daemon=True).start()
            self.sessions[sid], self._servers[sid] = s, srv
        return {"socket_path": path, "provider": provider, "model": conf["model"], "configuration": conf_name}

    def close_session(self, ctx: Ctx, p: dict) -> dict:
        sid = p.get("session_id")
        with self._lock:
            if sid in self._closed:
                return self._closed[sid]
            s, srv = self.sessions.pop(sid, None), self._servers.pop(sid, None)
        if s is None:
            raise RpcError("not_found", "no such session")
        srv.shutdown()
        srv.server_close()
        try:
            os.unlink(s.socket_path)  # MB-1: a leaked socket dies with the step
        except FileNotFoundError:
            pass
        m = s.meter()
        self._closed[sid] = m
        return m

    def meter(self, ctx: Ctx, p: dict) -> dict:
        s = self.sessions.get(p.get("session_id"))
        if s is None:
            if p.get("session_id") in self._closed:
                return self._closed[p["session_id"]]
            raise RpcError("not_found", "no such session")
        return s.meter()

    def admin_endpoint(self, path: str, controller_uids: set[int]) -> Endpoint:
        return Endpoint("model-broker-admin", path, "controller", controller_uids, {
            "open_session": self.open_session, "close_session": self.close_session, "meter": self.meter,
            "ping": lambda ctx, p: {"ok": True, "approved_providers": sorted(self.approved)},
        })

    # --- request path ----------------------------------------------------------------
    def handle(self, h: _Handler) -> None:
        s = h.server.session
        provider_seg, _, rest = h.path.partition("?")[0].lstrip("/").partition("/")
        rest = "/" + rest
        try:
            n = int(h.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_REQUEST:
                raise Refusal(400, "size", "request body missing or too large")
            raw = h.rfile.read(n)
            if provider_seg != s.provider:                                          # 2 route
                raise Refusal(403, "provider", f"this session is bound to {s.provider}")
            m = pv.path_ok(s.provider, rest)
            if not m:
                raise Refusal(403, "path", f"path {rest} not permitted")
            try:
                body = json.loads(raw)
            except ValueError as e:
                raise Refusal(400, "json", "request body must be JSON") from e
            if not isinstance(body, dict):
                raise Refusal(400, "json", "request body must be a JSON object")
            if pv.requested_model(s.provider, m, body) != s.model:                   # 3 model
                raise Refusal(403, "model", f"model not allowlisted for this session; pinned {s.model}")
            with s.lock:                                                            # 4 limits
                if s.requests >= s.max_requests:
                    raise Refusal(429, "limit_requests", "request limit reached")
                est_in = max(1, len(raw) // 4)
                if s.input_tokens + est_in > s.max_input_tokens:
                    raise Refusal(429, "limit_input_tokens", "input token limit reached")
                remaining = s.max_output_tokens - s.output_tokens
                usd_left = s.max_usd - s.usd - est_in * s.price_in
                if s.price_out > 0:
                    remaining = min(remaining, int(usd_left / s.price_out))
                if remaining < 1:
                    raise Refusal(429, "limit_output_or_usd", "output token or USD limit reached")
                clamp = pv.clamp_output(s.provider, rest, body, remaining)
                s.requests += 1
            stream = pv.is_stream(s.provider, rest, body)
            out_body = json.dumps(body).encode()
            status, resp_headers, resp = self._forward(h, s, rest, out_body, stream)  # 5-7
            usage = (pv.usage_from_stream(s.provider, resp) if stream else
                     pv.usage_from_json(s.provider, _json_or_none(resp)))
            if usage is None:
                usage = (est_in, clamp) if 200 <= status < 300 else (0, 0)          # conservative when unmetered
            with s.lock:                                                            # 8 meter
                s.input_tokens += usage[0]
                s.output_tokens += usage[1]
                s.usd += usage[0] * s.price_in + usage[1] * s.price_out
                if status >= 500 or status == 0:
                    s.upstream_errors += 1
            self._audit(s, "model_request", {"status": status, "stream": stream, "usage": list(usage),
                                             "request_sha256": sha256_hex(out_body), "response_sha256": sha256_hex(resp)},
                        {"request": out_body[:AUDIT_CAP].decode(errors="replace"), "response": resp[:AUDIT_CAP].decode(errors="replace")})
        except Refusal as r:
            with s.lock:
                s.refusals.append({"cause": r.cause, "message": r.message, "t": now()})
            self._audit(s, "model_refusal", {"cause": r.cause, "message": r.message})
            try:
                h._refuse(pv.error_body(s.provider, r.status, f"valops model broker refused: {r.message}"), r.status)
            except OSError:
                pass

    def _forward(self, h: _Handler, s: Session, rest: str, body: bytes, stream: bool) -> tuple[int, dict, bytes]:
        u = urlparse(s.upstream)
        headers = {k.lower(): v for k, v in h.headers.items() if k.lower() in pv.FORWARD_HEADERS[s.provider]}
        headers.update(pv.auth_headers(s.provider, self._keys[s.provider]))           # 6 inject
        if s.provider == "anthropic":
            headers.setdefault("anthropic-version", "2023-06-01")
        headers["content-type"] = "application/json"
        headers["content-length"] = str(len(body))
        path = (u.path.rstrip("/") + rest) + ("?alt=sse" if s.provider == "google" and stream else "")
        if u.scheme == "https":
            conn: http.client.HTTPConnection = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=300,
                                                                           context=ssl.create_default_context())
        else:  # tests only (allow_insecure_upstream)
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=300)
        captured = bytearray()
        try:
            conn.request("POST", path, body=body, headers=headers)
            r = conn.getresponse()
            h.send_response(r.status)
            ctype = r.getheader("Content-Type", "application/json")
            h.send_header("Content-Type", ctype)
            if stream and 200 <= r.status < 300:
                h.send_header("Transfer-Encoding", "chunked")
                h.end_headers()
                while True:
                    chunk = r.read1(65536) if hasattr(r, "read1") else r.read(65536)
                    if not chunk:
                        break
                    if len(captured) < MAX_RESPONSE:
                        captured.extend(chunk)
                    h.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    h.wfile.flush()
                h.wfile.write(b"0\r\n\r\n")
            else:
                data = r.read(MAX_RESPONSE)
                captured.extend(data)
                h.send_header("Content-Length", str(len(data)))
                h.end_headers()
                h.wfile.write(data)
            return r.status, dict(r.getheaders()), bytes(captured)
        except (OSError, http.client.HTTPException) as e:
            body_e = pv.error_body(s.provider, 502, f"upstream unreachable: {type(e).__name__}")
            try:
                h._refuse(body_e, 502)
            except OSError:
                pass
            return 0, {}, bytes(captured)
        finally:
            conn.close()

    def _audit(self, s: Session, event: str, data: dict, payload: Any = None) -> None:
        if self.audit is None:
            return
        try:
            self.audit.submit(event, s.episode_id, {**data, "session_id": s.session_id, "role": s.role,
                                                    "configuration": s.configuration, "model": s.model}, payload)
        except RpcError as e:
            log.error("audit submit failed: %s", e)


def _json_or_none(b: bytes) -> Any:
    try:
        return json.loads(b)
    except ValueError:
        return None
