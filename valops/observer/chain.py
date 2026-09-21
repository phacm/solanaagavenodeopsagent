"""Validator-host local hash chain (OD-10, SR-15).

The daemon records every request it served in its own chain and serves signed
checkpoints. The ops-host sequencer records each checkpoint and checks that the daemon's
hash at the previously recorded seq is unchanged, so truncation or rewrite of this file
is detectable from the ops host.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ..common.canonical import b64u, canonical, now, sha256_hex
from ..common.crypto import Signer

GENESIS = "0" * 64


class LocalChain:
    def __init__(self, path: str | os.PathLike, signer: Signer):
        self.path = Path(path)
        self.signer = signer
        self._lock = threading.Lock()
        self.hashes: dict[int, str] = {0: GENESIS}
        self.seq = 0
        if self.path.exists():
            prev = GENESIS
            for n, line in enumerate(self.path.read_bytes().splitlines(), 1):
                e = json.loads(line)
                if e["prev"] != prev or e["seq"] != n:
                    raise RuntimeError(f"local chain broken at {n}; refusing to start")
                prev = sha256_hex(canonical(e))
                self.hashes[n] = prev
                self.seq = n
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "ab")

    def append(self, data: dict) -> dict:
        with self._lock:
            e = {"seq": self.seq + 1, "ts": now(), "prev": self.hashes[self.seq], **data}
            self._fh.write(canonical(e) + b"\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self.seq += 1
            self.hashes[self.seq] = sha256_hex(canonical(e))
            return {"seq": self.seq, "hash": self.hashes[self.seq]}

    def checkpoint(self, since_seq: int | None) -> dict:
        with self._lock:
            since = since_seq if since_seq is not None and 0 <= since_seq <= self.seq else None
            ck = {"seq": self.seq, "head": self.hashes[self.seq], "ts": now(),
                  "since_seq": since, "since_head": self.hashes.get(since) if since is not None else None}
        ck["sig"] = b64u(self.signer.sign(canonical({k: ck[k] for k in ("seq", "head", "ts", "since_seq", "since_head")})))
        return ck
