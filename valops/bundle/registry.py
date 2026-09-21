"""Bundle registry: verification, binding, activation, drain, revocation, rollback (HLD §5.4).

Integrity is always checked against a *given* bundle id (the episode's bound id), never
against "whatever is mounted now". Any verification failure is reported as a reason
string; callers put the system in observe-only (§5.4 failure mode).
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

from ..common.canonical import b64u_dec, now, sha256_hex
from ..common.crypto import Verifier
from .builder import MANIFEST, SIG, compute_manifest


@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    verifier: Verifier
    status: str  # "active" | "retired" -- retired keys verify but cannot activate (D14)


class BundleError(Exception):
    pass


class Bundle:
    """Read-only accessor over a *verified* bundle directory."""

    def __init__(self, bundle_id: str, path: Path):
        self.id = bundle_id
        self.path = path

    def _y(self, rel: str) -> Any:
        with open(self.path / rel) as f:
            return yaml.safe_load(f)

    @cached_property
    def thresholds(self) -> dict:
        return self._y("thresholds.yaml")["parameters"]

    @cached_property
    def deployment(self) -> dict:
        return self._y("deployment.yaml")

    @cached_property
    def providers(self) -> dict:
        return self._y("providers.yaml")

    @cached_property
    def pricing(self) -> dict:
        return self._y("pricing.yaml")

    @cached_property
    def command_table(self) -> dict:
        return self._y("command_table.yaml")

    @cached_property
    def fault_classes(self) -> dict:
        return self._y("fault_classes.yaml")

    @cached_property
    def judge_checklist(self) -> dict:
        return self._y("judge_checklist.yaml")

    @cached_property
    def skills(self) -> dict:
        return (self._y("skills/index.yaml") or {}).get("skills") or {}

    @cached_property
    def verifier_rules(self) -> list[dict]:
        d = self.path / "verifier"
        return [self._y(f"verifier/{p.name}") for p in sorted(d.glob("*.yaml"))] if d.is_dir() else []

    def param(self, pid: str, key: str | None = None, configuration: str | None = None) -> Any:
        v = self.thresholds[pid]
        if isinstance(v, dict) and configuration and configuration in (v.get("by_configuration") or {}):
            v = {**v, **v["by_configuration"][configuration]}
        if key is not None:
            return v[key]
        return v

    def prompt_path(self, role: str, inlined: bool) -> Path:
        return self.path / "prompts" / (f"{role}.inlined.md" if inlined else f"{role}.md")

    def configuration_for(self, role: str) -> tuple[str, dict]:
        name = self.providers["roles"][role]
        return name, self.providers["configurations"][name]

    def skill_file(self, name: str) -> Path:
        return self.path / "skills" / name / "SKILL.md"


class BundleRegistry:
    def __init__(self, root: str | os.PathLike, trusted_keys: dict[str, TrustedKey]):
        self.root = Path(root)
        self.keys = trusted_keys
        self._lock = threading.Lock()

    # --- integrity -------------------------------------------------------------------
    def verify(self, bundle_id: str) -> str | None:
        """None if the bundle verifies and is not revoked; otherwise the reason."""
        if not bundle_id or not all(c in "0123456789abcdef" for c in bundle_id) or len(bundle_id) != 64:
            return "malformed bundle id"
        if bundle_id in self.revoked():
            return f"bundle {bundle_id[:12]} revoked"
        return self.verify_integrity(bundle_id)

    def verify_integrity(self, bundle_id: str) -> str | None:
        d = self.root / bundle_id
        if not d.is_dir():
            return f"bundle {bundle_id[:12]} not present"
        try:
            recorded = (d / MANIFEST).read_bytes()
            sigdoc = json.loads((d / SIG).read_text())
        except (OSError, ValueError) as e:
            return f"manifest/signature unreadable: {e}"
        actual = compute_manifest(d)
        if actual != recorded:
            changed = _diff_manifest(recorded, actual)
            return f"bundle content differs from manifest: {changed}"
        if sha256_hex(recorded) != bundle_id:
            return "manifest hash does not match bundle id"
        key = self.keys.get(sigdoc.get("key_id", ""))
        if key is None:
            return "manifest signed by an untrusted key"
        if not key.verifier.verify(b64u_dec(sigdoc["sig"]), recorded):
            return "manifest signature invalid"
        return None

    def load(self, bundle_id: str) -> Bundle:
        reason = self.verify(bundle_id)
        if reason:
            raise BundleError(reason)
        return Bundle(bundle_id, self.root / bundle_id)

    # --- lifecycle -------------------------------------------------------------------
    def active(self) -> str | None:
        try:
            return (self.root / "active").read_text().strip() or None
        except FileNotFoundError:
            return None

    def history(self) -> list[dict]:
        p = self.root / "active.history"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]

    def activate(self, bundle_id: str, *, by: str) -> None:
        with self._lock:
            reason = self.verify(bundle_id)
            if reason:
                raise BundleError(f"refusing to activate: {reason}")
            sigdoc = json.loads((self.root / bundle_id / SIG).read_text())
            if self.keys[sigdoc["key_id"]].status != "active":
                raise BundleError("bundle signed by a retired key cannot be activated (D14)")
            prev = self.active()
            tmp = self.root / ".active.tmp"
            tmp.write_text(bundle_id + "\n")
            os.replace(tmp, self.root / "active")
            with open(self.root / "active.history", "a") as f:
                f.write(json.dumps({"ts": now(), "active": bundle_id, "previous": prev, "by": by}) + "\n")
                f.flush()
                os.fsync(f.fileno())

    def rollback(self, *, by: str) -> str:
        """Re-point `active` at the bundle that preceded the current one (exact)."""
        hist = self.history()
        cur = self.active()
        for row in reversed(hist):
            if row["active"] == cur and row.get("previous"):
                self.activate(row["previous"], by=by)
                return row["previous"]
        raise BundleError("no previous bundle to roll back to")

    def revoked(self) -> set[str]:
        p = self.root / "revoked"
        if not p.exists():
            return set()
        return {json.loads(line)["id"] for line in p.read_text().splitlines() if line.strip()}

    def revoke(self, bundle_id: str, *, reason: str, by: str) -> None:
        with self._lock, open(self.root / "revoked", "a") as f:
            f.write(json.dumps({"id": bundle_id, "ts": now(), "reason": reason, "by": by}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def superseded_at(self, bundle_id: str) -> float | None:
        """When a different bundle was first activated after `bundle_id` (drain start)."""
        seen = False
        for row in self.history():
            if row["active"] == bundle_id:
                seen = True
            elif seen:
                return row["ts"]
        return None


def _diff_manifest(a: bytes, b: bytes) -> list[str]:
    def parse(m: bytes) -> dict[str, str]:
        out = {}
        for line in m.decode().splitlines():
            if line.strip():
                h, rel = line.split("  ", 1)
                out[rel] = h
        return out

    pa, pb = parse(a), parse(b)
    return sorted({k for k in pa.keys() | pb.keys() if pa.get(k) != pb.get(k)})[:10]
