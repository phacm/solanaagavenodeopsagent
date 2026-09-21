"""Typed argument validation and argv assembly (OD-2). No shell is ever involved."""
from __future__ import annotations

import re
from typing import Any

from .table import _PLACEHOLDER, Command

BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class ArgError(ValueError):
    pass


def validate_args(cmd: Command, args: Any) -> dict[str, Any]:
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ArgError("args must be an object")
    unknown = set(args) - set(cmd.args)
    if unknown:
        raise ArgError(f"unknown args {sorted(unknown)}")
    out: dict[str, Any] = {}
    for name, spec in cmd.args.items():
        if name not in args:
            if spec.required:
                raise ArgError(f"missing arg {name}")
            continue
        v = args[name]
        if spec.type == "int":
            if not isinstance(v, int) or isinstance(v, bool):
                raise ArgError(f"{name} must be an integer")
            if spec.min is not None and v < spec.min or spec.max is not None and v > spec.max:
                raise ArgError(f"{name} out of bounds [{spec.min}, {spec.max}]")
        elif spec.type == "pubkey":
            if not isinstance(v, str) or not BASE58.match(v):
                raise ArgError(f"{name} must be a base58 public key")
        out[name] = v
    return out


def assemble_argv(cmd: Command, args: dict[str, Any], local: dict[str, str]) -> list[str]:
    """Fill placeholders from validated args first, then daemon-local configuration."""
    def fill(tok: str) -> str:
        m = _PLACEHOLDER.match(tok)
        if not m:
            return tok
        key = m.group(1)
        if key in args:
            return str(args[key])
        if key in local:
            return str(local[key])
        raise ArgError(f"placeholder {key} has no value")

    argv = [fill(t) for t in cmd.argv]
    for name, toks in cmd.optional_argv.items():
        if name in args:
            argv += [fill(t) for t in toks]
    return argv
