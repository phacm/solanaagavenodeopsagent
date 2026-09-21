"""State transition table with authorised principals (HLD §7.2, R-7, DD-11)."""
from __future__ import annotations

STATES = ("open", "diagnosing", "recommending", "judging", "reporting", "awaiting_operator", "resolved", "handed_off")
TERMINAL = frozenset({"resolved", "handed_off"})
NONTERMINAL = tuple(s for s in STATES if s not in TERMINAL)

CONTROLLER = frozenset({
    ("open", "diagnosing"),
    ("diagnosing", "recommending"),
    ("diagnosing", "reporting"),
    ("recommending", "judging"),
    ("judging", "recommending"),
    ("judging", "reporting"),
    ("reporting", "awaiting_operator"),
    *((s, "handed_off") for s in NONTERMINAL),
})
# DD-11: the verifier may set `resolved` only from `awaiting_operator`, and it is the only
# principal that can (DD-4). The operation lives on an endpoint nobody else reaches.
VERIFIER = frozenset({("awaiting_operator", "resolved")})


def allowed(principal: str, frm: str, to: str) -> bool:
    table = {"controller": CONTROLLER, "verifier": VERIFIER}.get(principal, frozenset())
    return (frm, to) in table
