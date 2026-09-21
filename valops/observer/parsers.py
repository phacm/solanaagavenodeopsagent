"""Structured parsers for read-only command output (OD-4 "structured where parseable").

Output formats of `solana` / `agave-validator` are not a stable interface; every parser
here is a W2 verification item against the pinned Agave version [U]. A parser that
does not recognise its input returns ``{"parsed": False}`` -- it never guesses.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_US_THEM = re.compile(r"us:\s*(\d+)\s+them:\s*(\d+)")
_SOL = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s+SOL\b", re.M)
_VERSION = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_MONITOR_SLOT = re.compile(r"(?i)(processed|confirmed|finalized)[^\d]{0,10}(\d+)")
_SCHED = re.compile(r"^\s*(\d+)\s+([1-9A-HJ-NP-Za-km-z]{32,44})\s*$", re.M)


def catchup(text: str, local: dict) -> dict[str, Any]:
    m = _US_THEM.search(text)
    if not m:
        return {"parsed": False}
    us, them = int(m.group(1)), int(m.group(2))
    caught = "has caught up" in text
    return {"parsed": True, "our_slot": us, "cluster_slot": them, "slots_behind": max(0, them - us), "caught_up": caught}


def balance(text: str, local: dict) -> dict[str, Any]:
    m = _SOL.search(text)
    return {"parsed": True, "balance_sol": float(m.group(1))} if m else {"parsed": False}


def running_version(text: str, local: dict) -> dict[str, Any]:
    lines = [ln for ln in text.splitlines() if "Starting validator with" in ln or "agave-validator" in ln]
    for ln in reversed(lines):
        m = _VERSION.search(ln)
        if m:
            return {"parsed": True, "version": m.group(1)}
    return {"parsed": False}


def validator_monitor(text: str, local: dict) -> dict[str, Any]:
    slots = {k.lower(): int(v) for k, v in _MONITOR_SLOT.findall(text)}
    return {"parsed": bool(slots), **({"slots": slots} if slots else {})}


def leader_schedule_self(text: str, local: dict) -> dict[str, Any]:
    ident = local.get("identity_pubkey")
    slots = [int(s) for s, pk in _SCHED.findall(text) if pk == ident]
    if not slots and not _SCHED.search(text):
        return {"parsed": False}
    return {"parsed": True, "own_leader_slots": slots[:200], "count": len(slots)}


PARSERS: dict[str, Callable[[str, dict], dict[str, Any]]] = {
    "catchup": catchup, "balance": balance, "running_version": running_version,
    "validator_monitor": validator_monitor, "leader_schedule_self": leader_schedule_self,
}
