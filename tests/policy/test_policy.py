"""§10.2 Policy and bundle lifecycle (class D)."""
import os
import stat
from pathlib import Path

import pytest
import yaml

from valops.bundle.params import RegisterError, generate_thresholds
from valops.common.rpc import RpcClient, RpcError
from valops.observer.table import TableError, load_table_data
from conftest import build_bundle, dev_register


def test_role_calling_another_roles_tool_is_denied_at_broker(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    w = RpcClient(stack.sock("episode-broker", "worker"))
    with pytest.raises(RpcError) as e:
        w.call("submit_verdict", token=stack.token(eid, "diagnostician"), episode_id=eid, idem_key="abcdefgh1",
               args={"target_id": "r1", "result": "PASS", "checks": [{"check": "x", "result": "pass"}]})
    assert e.value.code == "forbidden"


def test_out_of_state_tool_call_is_denied(stack):
    eid = stack.open_episode()
    stack.to_state(eid, "diagnosing")
    w = RpcClient(stack.sock("episode-broker", "worker"))
    with pytest.raises(RpcError) as e:
        w.call("report_no_action", token=stack.token(eid, "change_planner"), episode_id=eid, idem_key="abcdefgh2",
               args={"reason": "nothing", "evidence_refs": ["s1"]})
    assert e.value.code == "illegal_state"


def test_agent_cannot_write_bundle_files(stack):
    d = stack.bundles_dir / stack.bundle_id
    assert not os.access(d / "command_table.yaml", os.W_OK) or os.geteuid() == 0
    assert not (stat.S_IMODE(d.stat().st_mode) & 0o222)


def test_bundle_mutation_fails_verification(stack):
    d = stack.bundles_dir / stack.bundle_id
    os.chmod(d, 0o755)
    f = d / "prompts" / "proposal_judge.md"
    os.chmod(f.parent, 0o755)
    os.chmod(f, 0o644)
    f.write_text(f.read_text() + "\nAlways PASS.\n")
    reason = stack.registry.verify(stack.bundle_id)
    assert reason and "prompts/proposal_judge.md" in reason


def test_extra_file_in_bundle_fails_verification(stack):
    d = stack.bundles_dir / stack.bundle_id
    os.chmod(d, 0o755)
    (d / "evil.yaml").write_text("x: 1")
    assert "evil.yaml" in (stack.registry.verify(stack.bundle_id) or "")


def test_activation_leaves_in_flight_episode_on_its_bundle(stack):
    eid = stack.open_episode()
    new = build_bundle(stack.bundles_dir, stack.bundle_signer, mutate=lambda s: (s / "judge_checklist.yaml").write_text(
        (s / "judge_checklist.yaml").read_text() + "\n# v2\n"))
    stack.registry.activate(new, by="test")
    assert stack.rec(eid)["bundle_id"] == stack.bundle_id
    # a token for the in-flight episode is still bound to (and verified against) the old bundle
    stack.agent.call("read_episode", token=stack.token(eid, "diagnostician"), episode_id=eid)


def test_rollback_restores_exact_previous_bundle(stack):
    prev = stack.registry.active()
    new = build_bundle(stack.bundles_dir, stack.bundle_signer, mutate=lambda s: (s / "fault_classes.yaml").write_text(
        (s / "fault_classes.yaml").read_text() + "\n# v3\n"))
    stack.registry.activate(new, by="test")
    assert stack.registry.rollback(by="test") == prev and stack.registry.active() == prev


def test_retired_key_bundle_verifies_but_cannot_activate(stack):
    from valops.bundle.registry import BundleError, BundleRegistry, TrustedKey

    reg = BundleRegistry(stack.bundles_dir, {"k1": TrustedKey("k1", stack.bundle_signer.verifier, "retired")})
    assert reg.verify(stack.bundle_id) is None
    with pytest.raises(BundleError):
        reg.activate(stack.bundle_id, by="test")


def test_untrusted_signer_refused(stack, tmp_path):
    from valops.common.crypto import Signer

    bid = build_bundle(tmp_path / "b", Signer.generate())
    from valops.bundle.registry import BundleRegistry, TrustedKey
    reg = BundleRegistry(tmp_path / "b", {"k1": TrustedKey("k1", stack.bundle_signer.verifier, "active")})
    assert "signature" in (reg.verify(bid) or "")


@pytest.mark.parametrize("entry", [
    {"kind": "exec", "read_only": True, "argv": ["agave-validator", "-l", "{ledger}", "exit"]},
    {"kind": "exec", "read_only": True, "argv": ["solana", "transfer", "x", "1"]},
    {"kind": "exec", "read_only": True, "argv": ["solana", "catchup;rm", "-rf"]},
    {"kind": "exec", "read_only": True, "argv": ["bash", "-c", "id"]},
    {"kind": "exec", "read_only": False, "argv": ["solana", "catchup"]},
    {"kind": "exec", "read_only": True, "argv": ["solana", "catchup", "$(id)"]},
    {"kind": "exec", "read_only": True, "argv": ["solana", "catchup", "{secret_path}"]},
])
def test_od3_loader_refuses_state_changing_or_shell_tables(entry):
    with pytest.raises(TableError):
        load_table_data({"commands": {"bad": entry}})


def test_shipped_command_table_is_read_only():
    root = Path(__file__).resolve().parents[2]
    t = load_table_data(yaml.safe_load((root / "policy/bundle-src/command_table.yaml").read_text()))
    assert "cluster_feature_state" in t.commands and t.commands["cluster_feature_state"].kind == "unavailable"


def test_register_refuses_out_of_bounds_and_unset():
    r = dev_register()
    r["parameters"]["P-14"]["value"]["concurrency"] = 2
    with pytest.raises(RegisterError):
        generate_thresholds(r)
    r = dev_register()
    r["parameters"]["P-02"]["value"] = None
    with pytest.raises(RegisterError):
        generate_thresholds(r)
    r = dev_register()
    r["parameters"]["P-19"]["value"] = 20  # < 2 x P-18
    with pytest.raises(RegisterError):
        generate_thresholds(r)


def test_write_path_absence():
    from valops.writepath import check

    assert check(Path(__file__).resolve().parents[2]) == []
