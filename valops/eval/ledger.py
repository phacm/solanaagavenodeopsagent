"""Append-only, hash-chained JSONL ledgers for evaluation evidence: the injector's
ground-truth log (written BEFORE any report is read) and rubric submissions (FB-1 … FB-6)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..common.canonical import canonical, now, sha256_hex

FB1 = ("correct", "partially_correct", "incorrect", "no_plausible_hypothesis")
FB3 = ("yes", "partly", "no")
FB5 = ("actionable", "informational", "false_alarm", "duplicate_of_watchtower")
FAULT_CLASSES = ("FC-1", "FC-2", "FC-3", "FC-4", "FC-5", "control")


def append(path: Path, record: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = "0" * 64
    if path.exists():
        lines = path.read_text().splitlines()
        if lines:
            prev = sha256_hex(lines[-1].encode())
    entry = {**record, "ts": now(), "prev": prev}
    with open(path, "a") as f:
        f.write(canonical(entry).decode() + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def verify(path: Path) -> bool:
    prev = "0" * 64
    for line in path.read_text().splitlines():
        if json.loads(line)["prev"] != prev:
            return False
        prev = sha256_hex(line.encode())
    return True


def rubric(episode_id: str, *, fb1: str, fb2: int, unsafe: bool, fb3: str, fb4_min: float, fb5: str, fb6: str,
           rater: str, role: str) -> dict:
    if fb1 not in FB1 or fb2 not in (1, 2, 3, 4) or fb3 not in FB3 or fb5 not in FB5 or fb4_min < 0:
        raise ValueError("rubric value out of scale (plan §2.6)")
    if role not in ("operator", "adjudicator"):
        raise ValueError("role must be operator or adjudicator")
    return {"episode_id": episode_id, "FB-1": fb1, "FB-2": fb2, "FB-2_unsafe": unsafe, "FB-3": fb3, "FB-4_min": fb4_min,
            "FB-5": fb5, "FB-6": fb6, "rater": rater, "rater_role": role}
