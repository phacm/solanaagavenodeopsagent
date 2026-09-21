"""§10.1 Principal authentication (class D). Dev boundaries: no G1 weight."""
import json
import os

import pytest

from valops.common.rpc import Endpoint, RpcClient, RpcError, RpcServer


def test_caller_supplied_actor_is_ignored(stack):
    c = RpcClient(stack.sock("audit", "episode_broker"))
    r = c.call("submit", event="tool_call", data={"x": 1}, actor="controller", principal="controller")
    lines = (stack.tmp / "chain.jsonl").read_text().splitlines()
    entry = json.loads(lines[r["seq"] - 1])
    assert entry["actor"] == "episode_broker"


def test_control_operation_on_agent_endpoint_is_unknown_method(stack):
    eid = stack.open_episode()
    with pytest.raises(RpcError) as e:
        stack.agent.call("set_state", episode_id=eid, state="resolved", expected_revision=1)
    assert e.value.code == "unknown_method"


def test_token_for_episode_a_refused_on_b(stack):
    a, b = stack.open_episode("delinquency"), stack.open_episode("balance")
    stack.to_state(b, "diagnosing")
    with pytest.raises(RpcError) as e:
        stack.agent.call("append_hypothesis", token=stack.token(a, "diagnostician"), episode_id=b, idem_key="k1",
                         hypothesis={"rank": 1, "claim": "c", "test": "t", "expected_evidence": "e"})
    assert e.value.code == "forbidden"


def test_role_a_token_refused_for_role_b_operation(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    with pytest.raises(RpcError) as e:
        stack.agent.call("append_hypothesis", token=stack.token(eid, "change_planner"), episode_id=eid, idem_key="k1",
                         hypothesis={"rank": 1, "claim": "c", "test": "t", "expected_evidence": "e"})
    assert e.value.code == "forbidden"


def test_expired_token_refused(stack):
    eid = stack.open_episode()
    with pytest.raises(RpcError) as e:
        stack.agent.call("read_episode", token=stack.token(eid, "diagnostician", ttl=-1), episode_id=eid)
    assert e.value.code == "token_expired"


def test_forged_token_refused(stack):
    from valops.common.crypto import Signer
    from valops.common.tokens import mint

    eid = stack.open_episode()
    forged = mint(Signer.generate(), episode_id=eid, role="diagnostician", session_id="s", bundle_id=stack.bundle_id, ttl_s=60)
    with pytest.raises(RpcError) as e:
        stack.agent.call("read_episode", token=forged, episode_id=eid)
    assert e.value.code == "unauthenticated"


def test_token_bound_to_revoked_bundle_refused(stack):
    eid = stack.open_episode()
    tok = stack.token(eid, "diagnostician")
    stack.registry.revoke(stack.bundle_id, reason="test", by="test")
    with pytest.raises(RpcError) as e:
        stack.agent.call("read_episode", token=tok, episode_id=eid)
    assert e.value.code == "bundle_refused"


def test_revoked_session_refused_at_broker(stack):
    eid = stack.open_episode()
    tok = stack.token(eid, "diagnostician", session="s-rev")
    w = RpcClient(stack.sock("episode-broker", "worker"))
    w.call("read_episode", token=tok, episode_id=eid)
    RpcClient(stack.sock("episode-broker", "admin")).call("revoke_session", session_id="s-rev")
    with pytest.raises(RpcError) as e:
        w.call("read_episode", token=tok, episode_id=eid)
    assert e.value.code == "token_revoked"


def test_peer_uid_not_permitted_is_denied(tmp_path):
    path = f"/tmp/vo-deny-{os.getpid()}.sock"
    srv = RpcServer([Endpoint("x", path, "controller", {os.getuid() + 12345}, {"ping": lambda c, p: 1})]).start()
    try:
        with pytest.raises(RpcError) as e:
            RpcClient(path).call("ping")
        assert e.value.code == "denied"
    finally:
        srv.stop()
