"""§10.1 Audit integrity (class D)."""
import json
import threading

import pytest

from valops.audit.sequencer import verify_chain
from valops.common.crypto import Signer
from valops.common.rpc import RpcClient, RpcError
from valops.observer.chain import LocalChain


def test_single_writer_under_concurrent_submitters(stack):
    def worker(principal):
        c = RpcClient(stack.sock("audit", principal))
        for i in range(25):
            c.call("submit", event="tool_call", data={"i": i})

    ts = [threading.Thread(target=worker, args=(p,)) for p in ("controller", "verifier", "episode_broker", "report_broker")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    lines = (stack.tmp / "chain.jsonl").read_text().splitlines()
    seqs = [json.loads(x)["seq"] for x in lines]
    assert seqs == list(range(1, len(lines) + 1))
    res = verify_chain(stack.tmp / "chain.jsonl", stack.anchor.list(), {"c1": stack.chain_signer.verifier})
    assert res["ok"], res


def test_local_rewrite_detected_against_anchor(stack):
    RpcClient(stack.sock("audit", "controller")).call("submit", event="alert", data={"x": "original"})
    stack.seq.anchor_now()
    path = stack.tmp / "chain.jsonl"
    lines = path.read_text().splitlines()
    # attacker rewrites an early entry and recomputes every later link (a wholesale rewrite)
    from valops.audit.sequencer import GENESIS, entry_hash
    from valops.common.canonical import canonical
    entries = [json.loads(x) for x in lines]
    entries[0]["data"] = {"forged": True}
    prev = GENESIS
    for e in entries:
        e["prev"] = prev
        prev = entry_hash(e)
    path.write_bytes(b"".join(canonical(e) + b"\n" for e in entries))
    res = verify_chain(path, stack.anchor.list(), {"c1": stack.chain_signer.verifier})
    assert not res["ok"] and any("rewrite" in e for e in res["errors"])


def test_truncation_detected_against_anchor(stack):
    RpcClient(stack.sock("audit", "controller")).call("submit", event="alert", data={})
    stack.seq.anchor_now()
    path = stack.tmp / "chain.jsonl"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:1]) + "\n")
    res = verify_chain(path, stack.anchor.list(), {"c1": stack.chain_signer.verifier})
    assert not res["ok"]


def test_forged_anchor_signature_rejected(stack):
    res = verify_chain(stack.tmp / "chain.jsonl", stack.anchor.list(), {"c1": Signer.generate().verifier})
    assert not res["ok"]


def test_daemon_chain_truncation_detected_at_ops_host(stack, tmp_path):
    dkey = Signer.generate()
    stack.seq.daemon_verifier = dkey.verifier
    chain = LocalChain(tmp_path / "d.jsonl", dkey)
    for i in range(5):
        chain.append({"request_id": str(i)})
    c = RpcClient(stack.sock("audit", "observer_broker"))
    c.call("record_daemon_checkpoint", **chain.checkpoint(None))
    # validator-host attacker truncates the daemon chain and restarts it
    (tmp_path / "d.jsonl").write_text("")
    chain2 = LocalChain(tmp_path / "d.jsonl", dkey)
    chain2.append({"request_id": "x"})
    with pytest.raises(RpcError) as e:
        c.call("record_daemon_checkpoint", **chain2.checkpoint(5))
    assert e.value.code == "integrity"


def test_daemon_checkpoint_only_from_observer_broker_socket(stack):
    with pytest.raises(RpcError) as e:
        RpcClient(stack.sock("audit", "controller")).call("record_daemon_checkpoint", seq=1)
    assert e.value.code == "unknown_method"


def test_store_writes_carry_audit_refs(stack):
    eid = stack.open_episode()
    rec = stack.rec(eid)
    assert all(s["audit_ref"].startswith("audit:") and s["audit_ref"] != "audit:none" for s in rec["signals"])
