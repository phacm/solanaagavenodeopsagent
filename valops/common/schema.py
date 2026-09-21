"""Minimal JSON-Schema subset validator (no third-party dependency in the trusted path).

Supports: type, properties, required, additionalProperties=false, enum, const,
minLength, maxLength, pattern, minimum, maximum, items, minItems, maxItems.
"""
from __future__ import annotations

import re
from typing import Any

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


class SchemaError(ValueError):
    pass


def validate(value: Any, schema: dict, path: str = "$") -> None:
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = False
        for ty in types:
            py = _TYPES[ty]
            if isinstance(value, bool) and ty in ("integer", "number"):
                continue
            if isinstance(value, py):
                ok = True
                break
        if not ok:
            raise SchemaError(f"{path}: expected {t}")
    if "const" in schema and value != schema["const"]:
        raise SchemaError(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise SchemaError(f"{path}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError(f"{path}: too long")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise SchemaError(f"{path}: does not match {schema['pattern']}")
        if not value.strip() and schema.get("minLength", 0) > 0:
            raise SchemaError(f"{path}: blank")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise SchemaError(f"{path}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaError(f"{path}: at most {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(value):
                validate(v, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for r in schema.get("required", []):
            if r not in value:
                raise SchemaError(f"{path}: missing {r}")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                raise SchemaError(f"{path}: unexpected {sorted(extra)}")
        for k, sub in props.items():
            if k in value:
                validate(value[k], sub, f"{path}.{k}")


def is_valid(value: Any, schema: dict) -> bool:
    try:
        validate(value, schema)
        return True
    except SchemaError:
        return False
