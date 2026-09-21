"""Loopback bridge inside the worker sandbox: 127.0.0.1:<port> -> the per-session model-broker
socket (HLD §5.12). It is the worker's only route to any model; the sandbox has no other
network. It carries bytes and adds nothing -- the broker authenticates the socket."""
from __future__ import annotations

import socket
import threading


def _pipe(a: socket.socket, b: socket.socket) -> None:
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def start(port: int, uds_path: str) -> socket.socket:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(16)

    def accept_loop() -> None:
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            u = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                u.connect(uds_path)
            except OSError:
                c.close()
                continue
            threading.Thread(target=_pipe, args=(c, u), daemon=True).start()
            threading.Thread(target=_pipe, args=(u, c), daemon=True).start()

    threading.Thread(target=accept_loop, name="model-bridge", daemon=True).start()
    return srv
