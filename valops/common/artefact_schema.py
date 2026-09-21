"""Structured-output schemas per role (HLD §5.8 step 2). Used as the Claude adapter's
`output_format` and as the shape every adapter prints on its final stdout line. They are
a CROSS-CHECK only: the stored artefact is authoritative."""
from __future__ import annotations

ARTEFACT_SCHEMA: dict[str, dict] = {
    "diagnostician": {"type": "object", "properties": {
        "hypothesis_ids": {"type": "array", "items": {"type": "string", "pattern": "^h[0-9]+$"}, "minItems": 1}},
        "required": ["hypothesis_ids"], "additionalProperties": False},
    "change_planner": {"type": "object", "properties": {
        "artefact_id": {"type": "string", "pattern": "^[rn][0-9]+$"}},
        "required": ["artefact_id"], "additionalProperties": False},
    "proposal_judge": {"type": "object", "properties": {
        "target_id": {"type": "string", "pattern": "^[rn][0-9]+$"},
        "result": {"type": "string", "enum": ["PASS", "FAIL"]}},
        "required": ["target_id", "result"], "additionalProperties": False},
    "reporter": {"type": "object", "properties": {
        "report_ref": {"type": "string", "pattern": "^report:sha256:[0-9a-f]{64}$"}},
        "required": ["report_ref"], "additionalProperties": False},
}
