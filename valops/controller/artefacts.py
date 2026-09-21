"""Artefact validation after every step (HLD §5.8, FR-12, R-8, R-9, W12).

Reads the EPISODE RECORD, never the transcript. A step that ends without its artefact has
failed however confident its prose; a Judge step without a verdict is never PASS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..common.artefact_schema import ARTEFACT_SCHEMA
from ..common.schema import is_valid


@dataclass(frozen=True)
class Validation:
    ok: bool
    reason: str = ""


def _fail(reason: str) -> Validation:
    return Validation(False, reason)


def validate_diagnostician(rec: dict, session: str) -> tuple[Validation, set[str]]:
    hs = [h for h in rec["hypotheses"] if h["step_session"] == session]
    if not hs:
        return _fail("missing artefact: no hypothesis written in this step"), set()
    for h in hs:
        if not all(isinstance(h.get(k), str) and h[k].strip() for k in ("claim", "test", "expected_evidence")):
            return _fail(f"hypothesis {h['id']} lacks a contract field"), set()
    ranks = sorted(h["rank"] for h in hs)
    if ranks != list(range(1, len(hs) + 1)):
        return _fail(f"ranks must be 1..{len(hs)} with no gaps, got {ranks}"), set()
    return Validation(True), {h["id"] for h in hs}


def validate_planner(rec: dict, session: str) -> tuple[Validation, str | None]:
    rs = [r for r in rec["recommendations"] if r.get("session_id") == session]
    ns = [n for n in rec["no_action"] if n.get("session_id") == session]
    if len(rs) + len(ns) != 1:
        return _fail(f"expected exactly one recommendation or no-action record, got {len(rs) + len(ns)}"), None
    art = (rs or ns)[0]
    if not art.get("evidence_refs"):
        return _fail("artefact has no evidence references"), None
    return Validation(True), art["id"]


def validate_judge(rec: dict, session: str) -> tuple[Validation, dict | None]:
    vs = [v for v in rec["verdicts"] if v.get("session_id") == session]
    if len(vs) != 1:
        return _fail("missing verdict (absence of a verdict is not consent)"), None
    v = vs[0]
    if v["result"] not in ("PASS", "FAIL") or not v.get("checks"):
        return _fail("verdict without a non-empty checks list"), None
    return Validation(True), v


def validate_reporter(rec: dict, session: str, kind: str, alerts: list[dict]) -> tuple[Validation, str | None]:
    rs = [r for r in rec["reports"] if r.get("session_id") == session and r["kind"] == kind]
    if not rs:
        return _fail(f"missing {kind} report ref"), None
    acked = [a for a in alerts if a.get("session_id") == session and a.get("kind") == kind and a.get("ack")]
    if not acked:
        return _fail(f"{kind} alert not dispatched/acknowledged by the sink"), None
    return Validation(True), rs[-1]["ref"]


def cross_check(role: str, structured: dict | None, stored: object) -> Validation:
    """Step 2: disagreement between structured output and the stored artefact is a step
    failure. No structured output is not a failure (not every adapter supplies one)."""
    if structured is None:
        return Validation(True)
    if not is_valid(structured, ARTEFACT_SCHEMA[role]):
        return _fail("structured output does not match its schema")
    if role == "diagnostician" and set(structured["hypothesis_ids"]) != stored:
        return _fail("structured output disagrees with stored hypotheses")
    if role == "change_planner" and structured["artefact_id"] != stored:
        return _fail("structured output disagrees with stored artefact")
    if role == "proposal_judge" and (structured["result"], structured["target_id"]) != (stored["result"], stored["target_id"]):
        return _fail("structured verdict disagrees with stored verdict")
    if role == "reporter" and structured["report_ref"] != stored:
        return _fail("structured report ref disagrees with stored report")
    return Validation(True)


def assert_judge_isolated(view: dict, rec: dict) -> None:
    """§10.2 Judge isolation: the controller asserts the Judge input contains no planner or
    diagnostician prose before the session starts."""
    forbidden_keys = {"hypotheses", "verdicts", "reports", "no_action", "recommendations", "steps", "cost"}
    present = forbidden_keys & set(view)
    if present:
        raise AssertionError(f"judge view carries {sorted(present)}")
    # The artefact under judgement is planner-written by definition; everything else must
    # be free of reasoning prose.
    blob = json.dumps({k: v for k, v in view.items() if k != "under_judgement"})
    for h in rec["hypotheses"]:
        for f in ("claim", "test", "expected_evidence"):
            if len(h[f]) >= 12 and h[f] in blob:
                raise AssertionError(f"judge view contains hypothesis {h['id']} {f}")
    for v in rec["verdicts"]:
        for c in v["checks"]:
            note = c.get("note") or ""
            if len(note) >= 12 and note in blob:
                raise AssertionError("judge view contains a prior verdict note")
