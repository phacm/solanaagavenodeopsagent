"""Parameter register (plan §13.2, D6) -> thresholds.yaml.

The builder refuses any value that is unset (``null`` -- *set at G0*), outside its bounds,
or that violates a cross-parameter rule. "A value outside its bounds cannot be activated:
the bundle builder refuses it." Widening a bound is a change-control item (plan §17.1).
"""
from __future__ import annotations

from typing import Any


class RegisterError(ValueError):
    pass


def _walk_nulls(v: Any, path: str) -> list[str]:
    if v is None:
        return [path]
    if isinstance(v, dict):
        out = []
        for k, sub in v.items():
            out += _walk_nulls(sub, f"{path}.{k}")
        return out
    return []


def _check_bounds(pid: str, value: Any, bounds: Any, path: str) -> None:
    if bounds is None:
        return
    if isinstance(bounds, dict) and ("min" in bounds or "max" in bounds or "eq" in bounds):
        vals = value.values() if isinstance(value, dict) else [value]
        for v in vals:
            if isinstance(v, dict):
                _check_bounds(pid, v, bounds, path)
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise RegisterError(f"{path}: {v!r} is not numeric")
            if "min" in bounds and v < bounds["min"]:
                raise RegisterError(f"{path}: {v} below bound {bounds['min']}")
            if "max" in bounds and v > bounds["max"]:
                raise RegisterError(f"{path}: {v} above bound {bounds['max']}")
            if "eq" in bounds and v != bounds["eq"]:
                raise RegisterError(f"{path}: {v} must equal {bounds['eq']}")
        return
    if isinstance(bounds, dict):
        if not isinstance(value, dict):
            raise RegisterError(f"{path}: expected a mapping")
        for k, b in bounds.items():
            if k not in value:
                raise RegisterError(f"{path}.{k}: missing")
            _check_bounds(pid, value[k], b, f"{path}.{k}")


def generate_thresholds(register: dict) -> dict:
    params = register.get("parameters") or {}
    missing = [p for p in (f"P-{i:02d}" for i in range(1, 32)) if p not in params]
    if missing:
        raise RegisterError(f"register lacks {missing}")
    out: dict[str, Any] = {}
    for pid, row in params.items():
        value = row.get("value")
        nulls = _walk_nulls(value, pid)
        if nulls and not row.get("not_bundled"):
            raise RegisterError(f"{', '.join(nulls)} unset (set at G0); refusing to build")
        _check_bounds(pid, value, row.get("bounds"), pid)
        if not row.get("not_bundled"):
            out[pid] = value
    # Cross-parameter rules (plan §13.2 bounds column).
    if out["P-10"] > out["P-11"]:
        raise RegisterError("P-10 token expiry must be <= P-11 step timeout")
    if out["P-19"] < 2 * out["P-18"]:
        raise RegisterError("P-19 max anchor lag must be >= 2 x P-18")
    if out["P-14"]["concurrency"] != 1:
        raise RegisterError("P-14 concurrency is fixed at 1 by design")
    if out["P-26"]["rpo_min"] > out["P-18"]:
        raise RegisterError("P-26 RPO must never exceed P-18")
    return {"register_version": register.get("register_version"), "parameters": out}
