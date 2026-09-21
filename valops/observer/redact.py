"""Output redaction and suspicious-instruction flagging (OD-4, SR-6, HLD §6.4).

Validator output is untrusted data. It is capped, redacted (filesystem paths, anything
key-like) and scanned for imperative text aimed at known commands. Flags are reported
alongside the output; nothing is ever obeyed.
"""
from __future__ import annotations

import re

# 64-byte keypair JSON arrays, long base58 strings (secret keys are 87-88 chars), PEM blocks,
# bearer tokens / API keys.
_KEYPAIR_ARRAY = re.compile(r"\[\s*(?:\d{1,3}\s*,\s*){31,}\d{1,3}\s*\]")
_LONG_B58 = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{64,}\b")
_PEM = re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.S)
_API_KEY = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{16,}|sk-ant-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{30,}|Bearer\s+[A-Za-z0-9._\-]{16,})")
_PATH = re.compile(r"(?<![\w.])/(?:home|root|etc|mnt|var|srv|opt|data)[^\s:\"',)]*")

_SUSPICIOUS = re.compile(
    r"(?i)\b(ignore (?:all |any )?(?:previous|prior) instructions|you (?:must|should) now|system prompt|"
    r"(?:run|execute|call|invoke)\s+(?:`)?(?:agave-validator|solana|systemctl|rm|curl|wget|sudo)\b|"
    r"set-identity|exit --force|withdraw|transfer\s+\d|submit_verdict|propose_recommendation|send_alert)"
)


def redact(text: str) -> tuple[str, int]:
    n = 0
    for pat, repl in ((_PEM, "[REDACTED-PEM]"), (_KEYPAIR_ARRAY, "[REDACTED-KEYPAIR]"), (_API_KEY, "[REDACTED-KEY]"),
                      (_LONG_B58, "[REDACTED-B58]"), (_PATH, "[PATH]")):
        text, k = pat.subn(repl, text)
        n += k
    return text, n


def suspicious(text: str) -> list[str]:
    return sorted({m.group(0)[:80] for m in _SUSPICIOUS.finditer(text)})[:20]


def cap(data: bytes, limit: int) -> tuple[bytes, bool]:
    return (data[:limit], True) if len(data) > limit else (data, False)
