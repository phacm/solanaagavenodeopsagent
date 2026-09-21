"""§10.2 Falsifiability, evidence bridge, rank and verdict contracts (class D)."""
import pytest

from valops.common.rpc import RpcError


def hyp(stack, eid, tok, rank, key, **over):
    h = {"rank": rank, "claim": "ledger volume full", "test": "disk headroom", "expected_evidence": "free < 5%", **over}
    return stack.agent.call("append_hypothesis", token=tok, episode_id=eid, idem_key=key, hypothesis=h)


@pytest.fixture
def diag(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    return eid, stack.token(eid, "diagnostician")


def test_hypothesis_without_test_rejected(stack, diag):
    eid, tok = diag
    with pytest.raises(RpcError) as e:
        hyp(stack, eid, tok, 1, "k", test="  ")
    assert e.value.code == "contract"


def test_duplicate_rank_in_step_rejected_and_step_session_stamped(stack, diag):
    eid, tok = diag
    hyp(stack, eid, tok, 1, "k1")
    with pytest.raises(RpcError):
        hyp(stack, eid, tok, 1, "k2")
    assert stack.rec(eid)["hypotheses"][0]["step_session"] == "sess-1"


def test_evidence_ref_to_uncollected_signal_rejected(stack, diag):
    eid, tok = diag
    hyp(stack, eid, tok, 1, "k1")
    with pytest.raises(RpcError) as e:
        stack.agent.call("append_hypothesis_status", token=tok, episode_id=eid, idem_key="k2", hypothesis_id="h1",
                         status="supported", evidence_refs=["s99"])
    assert "never collected" in e.value.message


def _to_recommending(stack, mode="tower"):
    eid = stack.open_episode(mode=mode)
    stack.to_state(eid, "diagnosing")
    hyp(stack, eid, stack.token(eid, "diagnostician", session="d"), 1, "k1")
    stack.to_state(eid, "recommending")
    return eid


REC = {"hypothesis_id": "h1", "action_text": "Fund the identity account", "skill": "identity-balance",
       "preconditions": ["balance below floor"], "expected_postcondition": "balance above floor", "evidence_refs": ["s1"]}


def test_mode_specific_skill_rejected_when_mode_unknown(stack):
    eid = _to_recommending(stack, mode="unknown")
    tok = stack.token(eid, "change_planner", session="p")
    with pytest.raises(RpcError) as e:
        stack.agent.call("append_recommendation", token=tok, episode_id=eid, idem_key="r",
                         recommendation={**REC, "skill": "failover-runbook-draft"})
    assert "unknown" in e.value.message
    stack.agent.call("append_recommendation", token=tok, episode_id=eid, idem_key="r2", recommendation=REC)


def test_only_one_artefact_per_planner_step(stack):
    eid = _to_recommending(stack)
    tok = stack.token(eid, "change_planner", session="p")
    stack.agent.call("append_recommendation", token=tok, episode_id=eid, idem_key="r1", recommendation=REC)
    with pytest.raises(RpcError):
        stack.agent.call("append_no_action", token=tok, episode_id=eid, idem_key="n1", reason="x", evidence_refs=["s1"])


def test_verdict_requires_checks_and_current_target(stack):
    eid = _to_recommending(stack)
    stack.agent.call("append_recommendation", token=stack.token(eid, "change_planner", session="p"), episode_id=eid,
                     idem_key="r1", recommendation=REC)
    stack.to_state(eid, "judging")
    tok = stack.token(eid, "proposal_judge", session="j")
    with pytest.raises(RpcError):
        stack.agent.call("append_verdict", token=tok, episode_id=eid, idem_key="v", target_id="r1", result="PASS", checks=[])
    with pytest.raises(RpcError):
        stack.agent.call("append_verdict", token=tok, episode_id=eid, idem_key="v", target_id="r9", result="PASS",
                         checks=[{"check": "x", "result": "pass"}])


def test_judge_view_contains_no_reasoning(stack):
    from valops.controller.artefacts import assert_judge_isolated

    eid = _to_recommending(stack)
    stack.agent.call("append_recommendation", token=stack.token(eid, "change_planner", session="p"), episode_id=eid,
                     idem_key="r1", recommendation=REC)
    stack.to_state(eid, "judging")
    view = stack.agent.call("read_episode", token=stack.token(eid, "proposal_judge", session="j"), episode_id=eid, view="full")
    assert view["view"] == "judge" and "hypotheses" not in view and "ledger volume full" not in str(view)
    assert view["skill"]["preconditions"]
    assert_judge_isolated(view, stack.rec(eid))


def test_store_is_append_only_at_the_database(stack):
    import sqlite3

    stack.open_episode()
    with pytest.raises(sqlite3.DatabaseError):
        stack.store._db.execute("UPDATE entries SET kind='x'")
    with pytest.raises(sqlite3.DatabaseError):
        stack.store._db.execute("DELETE FROM entries")
