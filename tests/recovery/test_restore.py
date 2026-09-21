"""§10.2 Backup and recovery (class D, dev boundaries): restore store, chain and bundles onto
a 'fresh host' (new directory), verify against the anchor, resume without duplicate appends,
and never roll back the revocation list."""
import shutil

from valops.audit.client import AuditClient
from valops.audit.sequencer import verify_chain
from valops.common.tokens import TokenGate
from valops.store.service import EpisodeStore


def test_restore_resumes_without_duplicates(stack, tmp_path):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    stack.seq.anchor_now()
    before = stack.rec(eid)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    import sqlite3
    src = sqlite3.connect(stack.tmp / "store.sqlite")
    dst = sqlite3.connect(fresh / "store.sqlite")
    src.backup(dst)  # online backup (P-26 RPO)
    dst.close()
    shutil.copy(stack.tmp / "chain.jsonl", fresh / "chain.jsonl")
    assert verify_chain(fresh / "chain.jsonl", stack.anchor.list(), {"c1": stack.chain_signer.verifier})["ok"]
    restored = EpisodeStore(fresh / "store.sqlite", stack.registry, TokenGate(stack.token_signer.verifier, stack.registry.verify),
                            AuditClient(stack.sock("audit", "store"), buffer=True))
    rec = restored._records[eid]
    assert rec["revision"] == before["revision"] and rec["state"] == "diagnosing"
    # an idempotent retry replayed after restore appends nothing
    from valops.common.rpc import Ctx
    ctx = Ctx("store-control", "controller", 0, 0)
    sig = before["signals"][0]
    n = rec["revision"]
    restored.append_signal(ctx, {"episode_id": eid, "snapshot": {"command_id": "catchup"}, "idem_key": "replay-1"})
    restored.append_signal(ctx, {"episode_id": eid, "snapshot": {"command_id": "catchup"}, "idem_key": "replay-1"})
    assert restored._records[eid]["revision"] == n + 1 and sig


def test_revocation_list_is_append_only(stack):
    stack.registry.revoke(stack.bundle_id, reason="t", by="t")
    text = (stack.bundles_dir / "revoked").read_text()
    stack.registry.revoke("0" * 64, reason="t2", by="t")
    assert (stack.bundles_dir / "revoked").read_text().startswith(text)
