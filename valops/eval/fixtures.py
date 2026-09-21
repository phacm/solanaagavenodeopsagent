"""Frozen fixture sets (plan §8.1): the hash is recorded BEFORE a run; a run against a set
whose hash changed counts for nothing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def fixture_hash(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.name != "FROZEN.json":
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def freeze(d: Path, by: str) -> str:
    fh = fixture_hash(d)
    frozen = d / "FROZEN.json"
    if frozen.exists():
        raise FileExistsError("fixture set already frozen; create a new set instead of editing this one")
    frozen.write_text(json.dumps({"sha256": fh, "by": by}))
    return fh


def verify(d: Path) -> str:
    rec = json.loads((d / "FROZEN.json").read_text())
    fh = fixture_hash(d)
    if fh != rec["sha256"]:
        raise ValueError(f"fixture set {d} changed after freezing: {fh} != {rec['sha256']}")
    return fh
