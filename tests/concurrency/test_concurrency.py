"""§10.2 Concurrency (class D): CAS, idempotency, recovery during analysis, terminal hand-off."""
import threading

import pytest

from valops.common.rpc import RpcClient, RpcError


def test_cas_race_exactly_one_transition_wins(stack):
    eid = stack.open_episode()
    rev = stack.rec(eid)["revision"]
    results = []

    def go(i):
        try:
            RpcClient(stack.sock("store", "control")).call("set_state", episode_id=eid, state="diagnosing",
                                                            expected_revision=rev, idem_key=f"race-{i}")
            results.append("ok")
        except RpcError as e:
            results.append(e.code)

    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("ok") == 1 and results.count("conflict") == 7


def test_duplicate_delivery_is_a_noop(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    args = dict(token=stack.token(eid, "diagnostician"), episode_id=eid, idem_key="same",
                hypothesis={"rank": 1, "claim": "c", "test": "t", "expected_evidence": "e"})
    a = stack.agent.call("append_hypothesis", **args)
    rev = stack.rec(eid)["revision"]
    b = stack.agent.call("append_hypothesis", **args)
    assert a == b and stack.rec(eid)["revision"] == rev and len(stack.rec(eid)["hypotheses"]) == 1


def test_open_is_deduplicated_per_class_check_validator(stack):
    a = stack.open_episode("delinquency")
    b = stack.open_episode("delinquency")
    assert a == b
    assert stack.open_episode("balance") != a


def _verifier(stack):
    from valops.verifier.verifier import Verifier

    return Verifier(stack.verify, RpcClient(stack.sock("observer-broker", "system")),
                    RpcClient(stack.sock("report-broker", "system")), stack.registry)


def _healthy(stack):
    stack.observer.set("catchup", {"slots_behind": 0, "caught_up": True})
    stack.observer.set("host_metrics", {"unit_active": True, "min_free_pct": 50})


def test_recovery_during_analysis_attaches_observation_and_changes_no_state(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    _healthy(stack)
    v = _verifier(stack)
    for _ in range(8):
        v.tick()
    rec = stack.rec(eid)
    assert rec["state"] == "diagnosing"
    assert len(rec["recovery_observations"]) == 1 and not rec["verifications"]


def test_verifier_resolves_only_from_awaiting_operator_after_window(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing", "reporting", "awaiting_operator")
    _healthy(stack)
    v = _verifier(stack)
    w = stack.registry.load(stack.bundle_id).param("P-17", "window")
    for _ in range(w - 1):
        v.tick()
    assert stack.rec(eid)["state"] == "awaiting_operator"
    v.tick()
    rec = stack.rec(eid)
    assert rec["state"] == "resolved" and rec["verifications"][-1]["result"] == "pass"
    assert rec["state_history"][-1]["by"] == "verifier"


def test_stale_or_missing_samples_never_confirm_recovery(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing", "reporting", "awaiting_operator")
    stack.observer.reachable = False
    v = _verifier(stack)
    for _ in range(10):
        v.tick()
    assert stack.rec(eid)["state"] == "awaiting_operator"


def test_handed_off_is_terminal_and_not_reopened(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "handed_off")
    with pytest.raises(RpcError) as e:
        stack.to_state(eid, "diagnosing")
    assert e.value.code == "terminal"
    _healthy(stack)
    _verifier(stack).tick()
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off" and "not reopened" in rec["recovery_observations"][-1]["note"]
    assert stack.open_episode() != eid  # a recurring signal opens a NEW episode


def test_controller_cannot_set_resolved(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing", "reporting", "awaiting_operator")
    with pytest.raises(RpcError) as e:
        stack.to_state(eid, "resolved")
    assert e.value.code == "forbidden_transition"
