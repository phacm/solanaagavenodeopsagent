"""§10.1 Model broker (class D) against a fake upstream provider."""
import http.client
import json
import socket

import pytest

from valops.common.rpc import RpcClient, RpcError


class UDSConn(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self.path_ = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path_)


def post(sock, path, body, headers=None):
    c = UDSConn(sock)
    c.request("POST", path, body=json.dumps(body), headers={"Content-Type": "application/json", **(headers or {})})
    r = c.getresponse()
    return r.status, json.loads(r.read())


@pytest.fixture
def session(stack):
    eid = stack.open_episode()
    admin = RpcClient(str(stack.run / "model-broker" / "admin.sock"))
    s = admin.call("open_session", session_id="mb-1", episode_id=eid, role="diagnostician", bundle_id=stack.bundle_id)
    yield admin, s["socket_path"]
    try:
        admin.call("close_session", session_id="mb-1")
    except RpcError:
        pass


MSG = {"model": "claude-opus-5", "max_tokens": 100000, "messages": [{"role": "user", "content": "hi"}]}


def test_credentials_stripped_and_key_injected(stack, session):
    _, sock = session
    st, _ = post(sock, "/anthropic/v1/messages", MSG, {"x-api-key": "worker-forged", "Authorization": "Bearer x", "Cookie": "c"})
    assert st == 200
    h = stack.provider.requests[-1]["headers"]
    assert h["x-api-key"] == "sk-real-key"
    assert "authorization" not in h and "cookie" not in h


def test_output_tokens_clamped_to_session_limit(stack, session):
    _, sock = session
    post(sock, "/anthropic/v1/messages", MSG)
    assert stack.provider.requests[-1]["body"]["max_tokens"] <= 64000


def test_wrong_provider_and_model_and_path_refused(stack, session):
    _, sock = session
    n = len(stack.provider.requests)
    assert post(sock, "/openai/v1/chat/completions", {**MSG, "model": "gpt-x"})[0] == 403
    assert post(sock, "/anthropic/v1/messages", {**MSG, "model": "claude-haiku-4-5"})[0] == 403
    assert post(sock, "/anthropic/v1/files", MSG)[0] == 403
    assert len(stack.provider.requests) == n  # nothing reached the provider


def test_request_limit_cuts_off_exactly(stack, session):
    admin, sock = session
    limit = admin.call("meter", session_id="mb-1")["limits"]["requests"]
    codes = [post(sock, "/anthropic/v1/messages", MSG)[0] for _ in range(limit + 2)]
    assert codes[:limit] == [200] * limit and codes[limit:] == [429, 429]
    m = admin.call("close_session", session_id="mb-1")
    assert m["requests"] == limit and any(r["cause"] == "limit_requests" for r in m["refusals"])
    assert m["input_tokens"] == 100 * limit and m["usd"] > 0


def test_session_socket_dies_with_the_step(stack, session):
    admin, sock = session
    admin.call("close_session", session_id="mb-1")
    with pytest.raises(OSError):
        post(sock, "/anthropic/v1/messages", MSG)


def test_unapproved_provider_is_unroutable(stack):
    eid = stack.open_episode()
    stack.model_broker.approved = set()
    with pytest.raises(RpcError) as e:
        RpcClient(str(stack.run / "model-broker" / "admin.sock")).call(
            "open_session", session_id="mb-2", episode_id=eid, role="diagnostician", bundle_id=stack.bundle_id)
    assert e.value.code == "provider_unapproved"


def test_transcript_hash_matches_request_sent(stack, session):
    from valops.common.canonical import sha256_hex

    _, sock = session
    post(sock, "/anthropic/v1/messages", MSG)
    sent = json.dumps(stack.provider.requests[-1]["body"]).encode()
    import time

    for _ in range(50):  # the broker audits after relaying the response
        entries = [json.loads(x) for x in (stack.tmp / "chain.jsonl").read_text().splitlines()]
        mrs = [e for e in entries if e["event"] == "model_request"]
        if mrs:
            break
        time.sleep(0.05)
    mr = mrs[-1]
    assert mr["actor"] == "model_broker"
    assert mr["data"]["request_sha256"] == sha256_hex(sent)


def test_worker_env_carries_no_provider_credential(stack):
    """The controller-generated step spec and runtime configs contain no real key."""
    from valops.worker.adapters.codex_cli.config import config_toml

    toml = config_toml(model="m", port=1, mcp_command=["python3", "-m", "x"])
    assert "sk-" not in toml and "VALOPS_PLACEHOLDER_KEY" in toml
