"""Consensus-mode determination (HLD §5.10, FR-8, W15).

Declared mode cross-checked against three observed inputs -- four inputs in total:
  1 declared mode (bundle deployment.yaml)
  2 running Agave version and its support for the mode (deployment.mode_support)
  3 cluster feature state (D9: query unverified => `unavailable` => disagreement)
  4 consensus state files present, with mtimes
All agreeing sets the mode. ANY disagreement -> `unknown`, every input recorded, alert,
and mode-specific recommendations prohibited.
"""
from __future__ import annotations

from typing import Any


def _vtuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def version_mode(version: str | None, support: dict) -> str | None:
    """support: {tower: {min: "x.y.z", max: "x.y.z"|null}, alpenglow: {...}} -> the single
    mode this version supports, or None if unknown/ambiguous."""
    if not version:
        return None
    try:
        v = _vtuple(version)
    except ValueError:
        return None
    modes = []
    for mode, r in (support or {}).items():
        lo = _vtuple(r["min"]) if r.get("min") else (0,)
        hi = _vtuple(r["max"]) if r.get("max") else (10**9,)
        if lo <= v <= hi:
            modes.append(mode)
    return modes[0] if len(modes) == 1 else None


def files_mode(files: dict | None) -> str | None:
    if not files or files.get("status") not in (None, "ok"):
        return None
    s = files.get("structured") or files
    tower, vh = bool(s.get("tower")), bool(s.get("vote_history"))
    if tower and not vh:
        return "tower"
    if vh and not tower:
        return "alpenglow"
    return None  # both present (migration / rollback / incomplete cleanup) or neither: ambiguous


def feature_mode(feature: dict | None) -> str | None:
    if not feature or feature.get("status") != "ok":
        return None  # `unavailable` until D9 closes -> counts as disagreement
    s = feature.get("structured") or {}
    return s.get("mode")


def determine(declared: str, running_version: dict | None, feature_state: dict | None,
              state_files: dict | None, support: dict) -> tuple[str, dict[str, Any]]:
    ver = ((running_version or {}).get("structured") or {}).get("version")
    observed = {
        "version": version_mode(ver, support),
        "feature_state": feature_mode(feature_state),
        "files": files_mode(state_files),
    }
    evidence = {
        "declared": declared,
        "version": {"running": ver, "implies": observed["version"]},
        "feature_state": {"status": (feature_state or {}).get("status", "unavailable"), "implies": observed["feature_state"]},
        "files": {"observed": (state_files or {}).get("structured"), "implies": observed["files"]},
    }
    agree = all(v == declared for v in observed.values())
    mode = declared if agree else "unknown"
    evidence["result"] = mode
    if not agree:
        evidence["disagreeing_inputs"] = sorted(k for k, v in observed.items() if v != declared)
    return mode, evidence
