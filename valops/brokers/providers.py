"""Provider wire-format knowledge used by the model broker: path allowlists, model
extraction, output-token clamping, usage extraction and provider-shaped errors.
Every entry is a W1 / W1-O / W1-G verification item on the pinned versions."""
from __future__ import annotations

import json
import re
from typing import Any

PATHS = {
    "anthropic": [re.compile(r"^/v1/messages$")],
    "openai": [re.compile(r"^/v1/chat/completions$"), re.compile(r"^/v1/responses$")],
    "google": [re.compile(r"^/v1beta/models/([A-Za-z0-9.\-_]+):(generateContent|streamGenerateContent)$")],
}
# Only these request headers are forwarded upstream; everything else (incl. every
# credential header) is dropped (MB step 5).
FORWARD_HEADERS = {
    "anthropic": {"content-type", "accept", "anthropic-version", "anthropic-beta"},
    "openai": {"content-type", "accept", "openai-beta"},
    "google": {"content-type", "accept"},
}
CREDENTIAL_HEADERS = {"authorization", "x-api-key", "x-goog-api-key", "api-key", "cookie", "proxy-authorization"}


def path_ok(provider: str, path: str) -> re.Match | None:
    for rx in PATHS[provider]:
        m = rx.match(path)
        if m:
            return m
    return None


def requested_model(provider: str, path_match: re.Match, body: dict) -> str | None:
    if provider == "google":
        return path_match.group(1)
    m = body.get("model")
    return m if isinstance(m, str) else None


def is_stream(provider: str, path: str, body: dict) -> bool:
    if provider == "google":
        return path.endswith(":streamGenerateContent")
    return bool(body.get("stream"))


def clamp_output(provider: str, path: str, body: dict, remaining: int) -> int:
    """Set the request's output cap to at most `remaining` so the limit cuts off exactly."""
    if provider == "anthropic":
        body["max_tokens"] = min(int(body.get("max_tokens") or remaining), remaining)
        return body["max_tokens"]
    if provider == "openai":
        if path.endswith("/responses"):
            body["max_output_tokens"] = min(int(body.get("max_output_tokens") or remaining), remaining)
            return body["max_output_tokens"]
        key = "max_tokens" if "max_tokens" in body else "max_completion_tokens"
        body[key] = min(int(body.get(key) or remaining), remaining)
        if body.get("stream"):
            body["stream_options"] = {**(body.get("stream_options") or {}), "include_usage": True}
        return body[key]
    gc = body.setdefault("generationConfig", {})
    gc["maxOutputTokens"] = min(int(gc.get("maxOutputTokens") or remaining), remaining)
    return gc["maxOutputTokens"]


def usage_from_json(provider: str, obj: Any) -> tuple[int, int] | None:
    if not isinstance(obj, dict):
        return None
    if provider == "anthropic":
        u = obj.get("usage") or (obj.get("message") or {}).get("usage")
        if isinstance(u, dict) and ("input_tokens" in u or "output_tokens" in u):
            i = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            return i, int(u.get("output_tokens") or 0)
        return None
    if provider == "openai":
        u = obj.get("usage") or (obj.get("response") or {}).get("usage")
        if isinstance(u, dict):
            i = u.get("prompt_tokens", u.get("input_tokens"))
            o = u.get("completion_tokens", u.get("output_tokens"))
            if i is not None or o is not None:
                return int(i or 0), int(o or 0)
        return None
    u = obj.get("usageMetadata")
    if isinstance(u, dict):
        return int(u.get("promptTokenCount") or 0), int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)
    return None


def usage_from_stream(provider: str, raw: bytes) -> tuple[int, int] | None:
    """Scan SSE `data:` lines (or a JSON array for Gemini without alt=sse)."""
    inp = out = None
    text = raw.decode(errors="replace")
    datas = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
    if not datas and provider == "google":
        try:
            arr = json.loads(text)
            datas = [json.dumps(x) for x in (arr if isinstance(arr, list) else [arr])]
        except ValueError:
            return None
    for d in datas:
        try:
            obj = json.loads(d)
        except ValueError:
            continue
        if provider == "anthropic":
            if obj.get("type") == "message_start":
                u = (obj.get("message") or {}).get("usage") or {}
                inp = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            elif obj.get("type") == "message_delta" and isinstance(obj.get("usage"), dict):
                out = int(obj["usage"].get("output_tokens") or 0)
                if "input_tokens" in obj["usage"] and obj["usage"]["input_tokens"]:
                    inp = int(obj["usage"]["input_tokens"])
        else:
            u = usage_from_json(provider, obj)
            if u:
                inp, out = u  # cumulative in the final chunk
    if inp is None and out is None:
        return None
    return int(inp or 0), int(out or 0)


def error_body(provider: str, status: int, message: str) -> bytes:
    if provider == "anthropic":
        t = {400: "invalid_request_error", 403: "permission_error", 429: "rate_limit_error"}.get(status, "api_error")
        return json.dumps({"type": "error", "error": {"type": t, "message": message}}).encode()
    if provider == "openai":
        return json.dumps({"error": {"message": message, "type": "invalid_request_error", "code": "valops_broker_refusal"}}).encode()
    s = {400: "INVALID_ARGUMENT", 403: "PERMISSION_DENIED", 429: "RESOURCE_EXHAUSTED"}.get(status, "INTERNAL")
    return json.dumps({"error": {"code": status, "message": message, "status": s}}).encode()


def auth_headers(provider: str, key: str) -> dict[str, str]:
    if provider == "anthropic":
        return {"x-api-key": key}
    if provider == "openai":
        return {"authorization": f"Bearer {key}"}
    return {"x-goog-api-key": key}
