"""External anchor stores (HLD §5.5, D15).

D15 default: object storage with compliance-mode retention lock in an account the ops
host cannot administer, written with a put-only credential (``S3AnchorStore``).
``FileAnchorStore`` is for development and tests only; it provides no protection
against an attacker on the ops host and carries no G1 weight (HLD §10.1).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class AnchorStore(Protocol):
    def put(self, anchor: dict) -> None: ...
    def list(self) -> list[dict]: ...


class FileAnchorStore:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def put(self, anchor: dict) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(anchor, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def list(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]


class S3AnchorStore:
    """Put-only writer. Objects are keyed by sequence so they never overwrite; the bucket
    must have Object Lock in COMPLIANCE mode (ER-7 failed-delete test proves it)."""

    def __init__(self, bucket: str, prefix: str, retention_days: int, region: str | None = None,
                 reader_profile: str | None = None):
        import boto3  # optional dependency: pip install valops-agent[s3]

        self._s3 = boto3.client("s3", region_name=region)
        self._reader = boto3.Session(profile_name=reader_profile).client("s3", region_name=region) if reader_profile else self._s3
        self.bucket, self.prefix, self.retention_days = bucket, prefix.rstrip("/"), retention_days

    def put(self, anchor: dict) -> None:
        from datetime import datetime, timedelta, timezone

        key = f"{self.prefix}/{anchor['seq']:020d}-{anchor['ts_ms']}.json"
        self._s3.put_object(
            Bucket=self.bucket, Key=key, Body=json.dumps(anchor, sort_keys=True).encode(),
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=datetime.now(timezone.utc) + timedelta(days=self.retention_days),
            ContentType="application/json",
        )

    def list(self) -> list[dict]:
        out = []
        pages = self._reader.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix + "/")
        for page in pages:
            for obj in page.get("Contents", []):
                body = self._reader.get_object(Bucket=self.bucket, Key=obj["Key"])["Body"].read()
                out.append(json.loads(body))
        return out


def from_config(cfg: dict) -> AnchorStore:
    kind = cfg.get("kind", "file")
    if kind == "file":
        return FileAnchorStore(cfg["path"])
    if kind == "s3":
        return S3AnchorStore(cfg["bucket"], cfg.get("prefix", "valops-anchors"), int(cfg["retention_days"]),
                             cfg.get("region"), cfg.get("reader_profile"))
    raise ValueError(f"unknown anchor store kind {kind}")
