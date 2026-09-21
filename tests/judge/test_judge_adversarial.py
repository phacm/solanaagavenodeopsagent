"""§10.2 Judge adversarial. Store-layer cases are class D and run always. Judge-layer cases
are class MQ: they need a real pinned model through the real model broker and run only
when VALOPS_MQ_ANTHROPIC_KEY_FILE is set (P-23 runs each, no-miss target)."""
import os
import uuid
from pathlib import Path

import pytest
import yaml

from valops.common.rpc import RpcError

CASES = yaml.safe_load((Path(__file__).resolve().parents[2] / "eval/fixtures/judge-adversarial-v1/cases.yaml").read_text())["cases"]


def seed(stack, case):
    eid = stack.open_episode(mode=case["mode"], signals=())
    for s in case["signals"]:
        stack.control.call("append_signal", episode_id=eid, snapshot={"command_id": s["command_id"], "status": "ok",
                                                                     "structured": s["structured"]}, idem_key=uuid.uuid4().hex)
    stack.to_state(eid, "diagnosing")
    stack.agent.call("append_hypothesis", token=stack.token(eid, "diagnostician", session="d"), episode_id=eid, idem_key="h",
                     hypothesis={"rank": 1, "claim": "validator behind cluster", "test": "catch-up distance", "expected_evidence": "> threshold"})
    stack.to_state(eid, "recommending")
    return eid


@pytest.mark.parametrize("case", [c for c in CASES if c["layer"] == "store"], ids=lambda c: c["id"])
def test_store_layer_rejects_before_the_judge(stack, case):
    eid = seed(stack, case)
    with pytest.raises(RpcError) as e:
        stack.agent.call("append_recommendation", token=stack.token(eid, "change_planner", session="p"), episode_id=eid,
                         idem_key="r", recommendation={"hypothesis_id": "h1", **case["recommendation"]})
    assert e.value.code == "contract"


@pytest.mark.skipif(not os.environ.get("VALOPS_MQ_ANTHROPIC_KEY_FILE"), reason="MQ: needs a real provider key (P-23 runs)")
@pytest.mark.parametrize("case", [c for c in CASES if c["layer"] == "judge"], ids=lambda c: c["id"])
def test_judge_fails_every_seeded_case(case):  # pragma: no cover - requires a live model
    pytest.skip("Run via the deployed topology: `valops` MQ harness against the pinned configuration (W17/W19).")
