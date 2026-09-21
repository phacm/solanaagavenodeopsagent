"""§10.2 Telemetry health (class D) and sentinel routing."""
from valops.audit.client import AuditClient
from valops.common.rpc import RpcClient
from valops.sentinel.scheduler import Sentinel


def sentinel(stack):
    return Sentinel(stack.control, RpcClient(stack.sock("observer-broker", "system")),
                    RpcClient(stack.sock("report-broker", "system")), AuditClient(stack.sock("audit", "controller"), buffer=True),
                    stack.registry)


def healthy(stack):
    stack.observer.set("host_metrics", {"unit_active": True, "unit_state": "active", "min_free_pct": 40})
    stack.observer.set("catchup", {"slots_behind": 0, "caught_up": True})
    stack.observer.set("identity_balance", {"balance_sol": 50.0})
    stack.observer.set("running_version", {"version": "2.2.0"})
    stack.observer.set("rpc_latency", {"latency_ms": 3, "healthy": True})


def classes(stack):
    return sorted((e["class"], e["trigger"]["check"]) for e in stack.control.call("list_episodes", nonterminal_only=True))


def test_healthy_validator_opens_nothing(stack):
    healthy(stack)
    sentinel(stack).tick()
    assert classes(stack) == []


def test_unit_stopped_opens_fc1_episode_with_signals(stack):
    healthy(stack)
    stack.observer.set("host_metrics", {"unit_active": False, "unit_state": "inactive", "min_free_pct": 40})
    sentinel(stack).tick()
    assert classes(stack) == [("validator_health", "unit_state")]
    eid = stack.control.call("list_episodes", nonterminal_only=True)[0]["episode_id"]
    assert stack.rec(eid)["signals"][0]["command_id"] == "host_metrics"


def test_delinquency_needs_consecutive_samples(stack):
    healthy(stack)
    stack.observer.set("catchup", {"slots_behind": 5000, "caught_up": False})
    s = sentinel(stack)
    s.tick()
    assert classes(stack) == []
    s.tick()
    assert classes(stack) == [("validator_health", "delinquency")]


def test_balance_disk_and_version_faults(stack):
    healthy(stack)
    stack.observer.set("identity_balance", {"balance_sol": 0.1})
    stack.observer.set("host_metrics", {"unit_active": True, "min_free_pct": 3})
    stack.observer.set("running_version", {"version": "2.1.9"})
    sentinel(stack).tick()
    assert classes(stack) == [("validator_health", "balance"), ("validator_health", "disk_headroom"),
                              ("validator_health", "version_drift")]


def test_observer_unreachable_opens_telemetry_episode_only(stack):
    """TH-1/TH-2: telemetry loss opens its own episode and never a validator-health one."""
    stack.observer.reachable = False
    s = sentinel(stack)
    s.tick()
    s.tick()
    assert classes(stack) == [("telemetry_health", "observer_unreachable")]


def test_telemetry_loss_does_not_touch_open_validator_episode(stack):
    healthy(stack)
    stack.observer.set("host_metrics", {"unit_active": False, "min_free_pct": 40})
    s = sentinel(stack)
    s.tick()
    vid = [e for e in stack.control.call("list_episodes", nonterminal_only=True)][0]["episode_id"]
    before = stack.rec(vid)
    stack.observer.reachable = False
    s.tick()
    after = stack.rec(vid)
    assert after["state"] == before["state"] and len(after["signals"]) == len(before["signals"])


def test_consensus_mode_unknown_while_feature_query_unverified(stack):
    healthy(stack)
    stack.observer.set("host_metrics", {"unit_active": False, "min_free_pct": 40})
    stack.observer.set("consensus_state_files", {"tower": [{"name": "tower-x.bin"}], "vote_history": []})
    sentinel(stack).tick()
    rec = stack.rec(stack.control.call("list_episodes", nonterminal_only=True)[0]["episode_id"])
    assert rec["consensus_mode"] == "unknown"
    assert "feature_state" in rec["consensus_mode_evidence"]["disagreeing_inputs"]
