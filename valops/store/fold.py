"""The episode record (HLD §7.1) is a fold over the append-only entry log."""
from __future__ import annotations

import copy
from typing import Any

from ..common.canonical import rfc3339


def empty_record(episode_id: str) -> dict:
    return {
        "episode_id": episode_id, "revision": 0, "class": None, "opened_at": None, "trigger": None,
        "validator_id": None, "policy_bundle": None, "bundle_id": None,
        "consensus_mode": None, "consensus_mode_evidence": {},
        "signals": [], "hypotheses": [], "recommendations": [], "no_action": [], "verdicts": [],
        "approvals": [], "executions": [],  # empty in M0 by construction (plan §5.7)
        "verifications": [], "recovery_observations": [], "reports": [], "annotations": [], "steps": [],
        "state": None, "state_history": [], "cost": {"per_role_usd": {}, "turns": {}, "by_session": {}},
    }


def apply(rec: dict, e: dict) -> None:
    """Apply one entry row (dict with rev, ts, kind, body, principal, session_id, audit_ref)."""
    k, b, t = e["kind"], e["body"], rfc3339(e["ts"])
    rec["revision"] = e["rev"]
    if k == "opened":
        rec.update({
            "class": b["class"], "opened_at": t, "opened_ts": e["ts"], "trigger": b["trigger"],
            "validator_id": b["validator_id"], "bundle_id": b["bundle_id"], "policy_bundle": "sha256:" + b["bundle_id"],
            "consensus_mode": b["consensus_mode"], "consensus_mode_evidence": b.get("consensus_mode_evidence", {}),
            "state": "open", "dedupe_key": b["dedupe_key"],
        })
        rec["state_history"].append({"t": t, "ts": e["ts"], "to": "open", "by": e["principal"], "rev": e["rev"]})
    elif k == "signal":
        rec["signals"].append({**b, "t": t, "audit_ref": e["audit_ref"]})
    elif k == "hypothesis":
        rec["hypotheses"].append({**b, "status": "open", "evidence_refs": [], "t": t})
    elif k == "hypothesis_status":
        for h in rec["hypotheses"]:
            if h["id"] == b["hypothesis_id"]:
                h["status"], h["evidence_refs"] = b["status"], b["evidence_refs"]
                h.setdefault("status_history", []).append({"t": t, "status": b["status"], "session_id": e["session_id"]})
    elif k == "recommendation":
        rec["recommendations"].append({**b, "session_id": e["session_id"], "t": t, "rev": e["rev"]})
    elif k == "no_action":
        rec["no_action"].append({**b, "session_id": e["session_id"], "t": t, "rev": e["rev"]})
    elif k == "verdict":
        rec["verdicts"].append({**b, "recommendation": b["target_id"], "session_id": e["session_id"], "t": t})
    elif k == "report":
        rec["reports"].append({**b, "session_id": e["session_id"], "t": t})
    elif k == "verification":
        rec["verifications"].append({**b, "t": t, "by": "verifier"})
    elif k == "recovery_observation":
        rec["recovery_observations"].append({**b, "t": t})
    elif k == "state":
        rec["state"] = b["to"]
        rec["state_history"].append({"t": t, "ts": e["ts"], "from": b["from"], "to": b["to"], "by": e["principal"],
                                     "rev": e["rev"], "reason": b.get("reason")})
    elif k == "cost":
        role = b["role"]
        c = rec["cost"]
        c["per_role_usd"][role] = round(c["per_role_usd"].get(role, 0.0) + b["usd"], 6)
        c["turns"][role] = c["turns"].get(role, 0) + b["turns"]
        c["by_session"][b["session_id"]] = {k2: b[k2] for k2 in ("role", "usd", "turns", "configuration", "tokens") if k2 in b}
    elif k == "step":
        rec["steps"].append({**b, "t": t, "ts": e["ts"]})
    elif k == "annotation":
        rec["annotations"].append({**b, "t": t})
    else:  # pragma: no cover - schema guarantees kinds
        raise ValueError(f"unknown entry kind {k}")


def fold(entries: list[dict]) -> dict:
    if not entries:
        raise KeyError("no such episode")
    rec = empty_record(entries[0]["episode_id"])
    for e in entries:
        apply(rec, e)
    return rec


def top_hypothesis(rec: dict) -> dict | None:
    """Rank-1 hypothesis of the latest *completed* diagnosis step (§7.1). A later
    `refuted` status does not re-rank it."""
    done = [s for s in rec["steps"] if s["role"] == "diagnostician" and s["outcome"] == "ok"]
    if not done:
        return None
    sess = done[-1]["session_id"]
    for h in rec["hypotheses"]:
        if h["step_session"] == sess and h["rank"] == 1:
            return h
    return None


def under_judgement(rec: dict) -> dict | None:
    """The latest recommendation or no-action record (whichever was written last)."""
    cands = rec["recommendations"] + rec["no_action"]
    return max(cands, key=lambda x: x["rev"]) if cands else None


def judge_view(rec: dict, skills: dict) -> dict:
    """SR-12: raw signals, the artefact under judgement, and the skill preconditions only.
    Never hypothesis prose, planner rationale, prior verdicts, or reports. Verifier records
    are included because they are deterministic observations, not reasoning, and HLD §7.5
    gives the Judge `get_verification_result`."""
    target = under_judgement(rec)
    target_c = copy.deepcopy(target) if target else None
    if target_c:
        for k in ("session_id", "rev"):
            target_c.pop(k, None)
    skill = None
    if target_c and "skill" in target_c:
        s = skills.get(target_c["skill"]) or {}
        skill = {"name": target_c["skill"], "modes": s.get("modes"), "preconditions": s.get("preconditions", [])}
    return {
        "view": "judge", "episode_id": rec["episode_id"], "class": rec["class"], "trigger": rec["trigger"],
        "state": rec["state"], "consensus_mode": rec["consensus_mode"],
        "consensus_mode_evidence": rec["consensus_mode_evidence"],
        "signals": copy.deepcopy(rec["signals"]), "under_judgement": target_c, "skill": skill,
        "verifications": copy.deepcopy(rec["verifications"]),
        "recovery_observations": copy.deepcopy(rec["recovery_observations"]),
    }


def full_view(rec: dict) -> dict:
    v = copy.deepcopy(rec)
    v["view"] = "full"
    v.pop("dedupe_key", None)
    v["top_hypothesis"] = top_hypothesis(rec)
    return v


VIEW_BY_ROLE: dict[str, str] = {
    "diagnostician": "full", "change_planner": "full", "proposal_judge": "judge", "reporter": "full",
}


def view_for(rec: dict, view: str, skills: dict) -> dict[str, Any]:
    if view == "judge":
        return judge_view(rec, skills)
    return full_view(rec)
