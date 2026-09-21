"""Ops-host configuration and the socket layout shared by every process class.

Each process class runs under its own uid (HLD §4.3); ``uids`` maps class -> allowed
peer uids and is what every endpoint checks with SO_PEERCRED. ``dev_single_uid: true``
maps every class to the current uid -- a development convenience that carries NO gate
weight (HLD §10.1 "real boundaries").
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .bundle.registry import BundleRegistry, TrustedKey
from .common.crypto import Verifier

CLASSES = ("controller", "worker", "verifier", "episode_broker", "observer_broker", "report_broker", "model_broker",
           "audit_sequencer", "store", "operator")


@dataclass
class Paths:
    run: Path

    def store(self, name: str) -> str:
        return str(self.run / "store" / f"{name}.sock")

    def audit(self, principal: str) -> str:
        return str(self.run / "audit" / f"{principal}.sock")

    def broker(self, broker: str, name: str) -> str:
        return str(self.run / broker / f"{name}.sock")

    @property
    def model_sessions(self) -> Path:
        return self.run / "model-broker" / "sessions"


class Config:
    def __init__(self, data: dict[str, Any], path: str | None = None):
        self.data = data
        self.path = path
        self.development = bool(data.get("development", False))
        self.paths = Paths(Path(data.get("runtime_dir", "/run/valops")))
        self.state = Path(data.get("state_dir", "/var/lib/valops"))
        if data.get("dev_single_uid"):
            if not self.development:
                raise ValueError("dev_single_uid requires development: true")
            me = os.getuid()
            self.uids = {c: {me} for c in CLASSES}
        else:
            self.uids = {c: set(data["uids"][c]) for c in CLASSES}

    @classmethod
    def load(cls, path: str) -> "Config":
        with open(path) as f:
            return cls(yaml.safe_load(f), path)

    def __getitem__(self, k: str) -> Any:
        return self.data[k]

    def get(self, k: str, default: Any = None) -> Any:
        return self.data.get(k, default)

    def bundles(self) -> BundleRegistry:
        keys = {}
        for k in self.data["keys"]["bundle_trusted"]:
            keys[k["key_id"]] = TrustedKey(k["key_id"], Verifier.load(k["public"]), k.get("status", "active"))
        return BundleRegistry(self.data.get("bundles_dir", self.state / "bundles"), keys)

    def token_verifier(self) -> Verifier:
        return Verifier.load(self.data["keys"]["token_public"])

    def anchor_keys(self) -> dict[str, Verifier]:
        k = self.data["keys"]
        return {k["chain_key_id"]: Verifier.load(k["chain_public"])}
