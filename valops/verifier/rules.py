"""Declarative verifier predicates (HLD §5.6).

Rules are data evaluated by code: a per-signal predicate (lt/le/gt/ge/eq/ne/in) composed
with all_of/any_of, plus a stability window. Never a string expression, never a model.
Values may reference the parameter register: ``{param: P-03, key: threshold}``.
"""
from __future__ import annotations

from typing import Any, Callable

OPS: dict[str, Callable[[Any, Any], bool]] = {
    "lt": lambda a, b: a < b, "le": lambda a, b: a <= b, "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b, "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "in": lambda a, b: a in b,
}
CLASSES = ("validator_health", "telemetry_health")


class RuleError(ValueError):
    pass


def _validate_pred(p: Any, where: str) -> None:
    if not isinstance(p, dict) or len(p) == 0:
        raise RuleError(f"{where}: predicate must be a mapping")
    if "all_of" in p or "any_of" in p:
        key = "all_of" if "all_of" in p else "any_of"
        if set(p) != {key} or not isinstance(p[key], list) or not p[key]:
            raise RuleError(f"{where}: {key} must be a non-empty list and alone")
        for i, sub in enumerate(p[key]):
            _validate_pred(sub, f"{where}.{key}[{i}]")
        return
    if set(p) != {"field", "op", "value"}:
        raise RuleError(f"{where}: leaf needs exactly field/op/value")
    if p["op"] not in OPS:
        raise RuleError(f"{where}: unknown op {p['op']}")
    if not isinstance(p["field"], str) or "." not in p["field"]:
        raise RuleError(f"{where}: field must be <command_id>.<path>")


def validate_rule(rule: dict, name: str) -> None:
    for k in ("id", "applies_to", "samples", "predicate", "window"):
        if k not in rule:
            raise RuleError(f"{name}: missing {k}")
    if rule["applies_to"].get("class") not in CLASSES:
        raise RuleError(f"{name}: applies_to.class must be one of {CLASSES}")
    if not isinstance(rule["samples"], list) or not rule["samples"]:
        raise RuleError(f"{name}: samples must list command ids")
    _validate_pred(rule["predicate"], name)
    for leaf_field in _fields(rule["predicate"]):
        if leaf_field.split(".", 1)[0] not in rule["samples"] and not leaf_field.startswith("telemetry."):
            raise RuleError(f"{name}: field {leaf_field} not produced by a sampled command")


def _fields(p: dict) -> list[str]:
    if "all_of" in p or "any_of" in p:
        return [f for sub in p.get("all_of", p.get("any_of", [])) for f in _fields(sub)]
    return [p["field"]]


def resolve(value: Any, param: Callable[[str, str | None], Any]) -> Any:
    if isinstance(value, dict) and "param" in value:
        return param(value["param"], value.get("key"))
    return value


def _get(sample: dict, path: str) -> Any:
    cur: Any = sample
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return cur


def evaluate(pred: dict, sample: dict, param: Callable[[str, str | None], Any]) -> bool:
    """True iff the predicate holds. A missing field makes the leaf False: absence of
    data never confirms recovery (TH-2, TH-3)."""
    if "all_of" in pred:
        return all(evaluate(p, sample, param) for p in pred["all_of"])
    if "any_of" in pred:
        return any(evaluate(p, sample, param) for p in pred["any_of"])
    try:
        actual = _get(sample, pred["field"])
    except KeyError:
        return False
    try:
        return bool(OPS[pred["op"]](actual, resolve(pred["value"], param)))
    except TypeError:
        return False


def window(rule: dict, param: Callable[[str, str | None], Any]) -> int:
    return int(resolve(rule["window"], param))
