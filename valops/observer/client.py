"""mTLS client for the observer daemon; held only by the observer broker (HLD §4.3)."""
from __future__ import annotations

import http.client
import json
import ssl
import time
import uuid
from urllib.parse import urlparse


class ObserverUnreachable(Exception):
    pass


class ObserverClient:
    def __init__(self, url: str, *, client_cert: str | None = None, client_key: str | None = None,
                 ca: str | None = None, timeout: float = 30.0):
        u = urlparse(url)
        self.host, self.port, self.tls = u.hostname, u.port or (443 if u.scheme == "https" else 80), u.scheme == "https"
        self.timeout = timeout
        self._ctx = None
        if self.tls:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
            if client_cert:
                ctx.load_cert_chain(client_cert, client_key)
            self._ctx = ctx

    def _conn(self) -> http.client.HTTPConnection:
        if self.tls:
            return http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=self._ctx)
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def _req(self, method: str, path: str, body: dict | None = None) -> tuple[dict, float]:
        t0 = time.monotonic()
        c = self._conn()
        try:
            data = json.dumps(body).encode() if body is not None else None
            c.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
            r = c.getresponse()
            payload = json.loads(r.read(2 * 1024 * 1024))
            if r.status != 200:
                raise ObserverUnreachable(f"HTTP {r.status}: {payload}")
            return payload, (time.monotonic() - t0) * 1000
        except (OSError, ssl.SSLError, http.client.HTTPException, ValueError) as e:
            raise ObserverUnreachable(f"{type(e).__name__}: {e}") from e
        finally:
            c.close()

    def observe(self, command_id: str, args: dict | None = None) -> tuple[dict, float]:
        return self._req("POST", "/observe", {"command_id": command_id, "args": args or {}, "request_id": str(uuid.uuid4())})

    def checkpoint(self, since: int | None) -> dict:
        return self._req("GET", "/checkpoint" + (f"?since={since}" if since is not None else ""))[0]

    def health(self) -> tuple[dict, float]:
        return self._req("GET", "/health")
