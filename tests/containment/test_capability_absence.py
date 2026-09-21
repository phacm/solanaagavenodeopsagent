"""§10.1 Capability absence (class D): asserted against the SERVED method list, not by
attempting and catching."""
from valops.common.rpc import RpcClient

FORBIDDEN = {"set_state", "append_verification", "append_recovery_observation", "resolve", "close_episode",
             "open_episode", "append_signal", "append_cost", "append_step"}


def test_agent_endpoints_have_no_closure_or_transition(stack):
    for sock in (stack.sock("store", "agent"), stack.sock("store", "agent-report")):
        served = set(RpcClient(sock).methods())
        assert not served & FORBIDDEN, served & FORBIDDEN


def test_worker_facing_broker_sockets_have_no_closure_or_transition(stack):
    for broker in ("episode-broker", "observer-broker", "report-broker"):
        served = set(RpcClient(stack.sock(broker, "worker")).methods())
        assert not served & FORBIDDEN, (broker, served & FORBIDDEN)
        assert "revoke_session" not in served and "open_session" not in served


def test_verify_endpoint_is_the_only_one_with_verification(stack):
    assert "append_verification" in RpcClient(stack.sock("store", "verify")).methods()
    assert "append_verification" not in RpcClient(stack.sock("store", "control")).methods()


def test_verifier_endpoint_cannot_set_any_state_but_resolved(stack):
    import pytest

    from valops.common.rpc import RpcError

    eid = stack.open_episode()
    with pytest.raises(RpcError) as e:
        stack.verify.call("set_state", episode_id=eid, state="handed_off", expected_revision=stack.rec(eid)["revision"])
    assert e.value.code == "forbidden_transition"
