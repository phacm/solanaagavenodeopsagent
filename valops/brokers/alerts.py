"""Alert sinks for the D5 channel. Only the report broker holds the channel credential."""
from __future__ import annotations

import json
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Protocol


class AlertSink(Protocol):
    def send(self, target: str, alert: dict) -> str: ...


def render_text(a: dict) -> str:
    lines = [f"[{a.get('severity', '?').upper()}] {a.get('title', '')}"]
    for k in ("fault_class", "top_hypothesis", "recommendation", "judge_verdict", "report", "episode_id"):
        if a.get(k):
            lines.append(f"{k.replace('_', ' ')}: {a[k]}")
    if a.get("summary"):
        lines.append(f"summary (model-written): {a['summary']}")
    if a.get("text"):
        lines.append(a["text"])
    if a.get("development"):
        lines.insert(0, "DEVELOPMENT RUN - no gate weight")
    return "\n".join(lines)


class FileSink:
    """Development sink: appends alerts as JSON lines."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, target: str, alert: dict) -> str:
        ack = "file:" + uuid.uuid4().hex[:12]
        with open(self.path, "a") as f:
            f.write(json.dumps({"target": target, "ack": ack, **alert, "text_rendered": render_text(alert)}) + "\n")
        return ack


class WebhookSink:
    """Slack / Discord / generic incoming webhook. URLs are read from files readable only
    by the report broker uid (the channel credential, HLD §4.3)."""

    def __init__(self, url_files: dict[str, str], style: str = "slack", timeout: float = 10.0):
        self.urls = {t: Path(p).read_text().strip() for t, p in url_files.items()}
        self.style, self.timeout = style, timeout

    def send(self, target: str, alert: dict) -> str:
        url = self.urls[target]
        text = render_text(alert)
        body = {"content": text[:1900]} if self.style == "discord" else {"text": text}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if not 200 <= r.status < 300:
                raise OSError(f"webhook HTTP {r.status}")
        return f"webhook:{target}:{uuid.uuid4().hex[:12]}"


def from_config(cfg: dict) -> AlertSink:
    if cfg.get("kind", "file") == "file":
        return FileSink(cfg["path"])
    if cfg["kind"] == "webhook":
        for p in cfg["url_files"].values():
            if os.stat(p).st_mode & 0o077:
                raise PermissionError(f"{p} must not be group/world readable")
        return WebhookSink(cfg["url_files"], cfg.get("style", "slack"))
    raise ValueError(f"unknown alert sink {cfg['kind']}")
