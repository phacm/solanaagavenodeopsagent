"""Controller state machine end to end over the real store and brokers, with a scripted
worker in place of a model (§8 worked example; §10.2 artefact completeness). No model is
called; this is control-plane evidence only."""
import pytest

from valops.common.rpc import RpcClient


def ok(res):
    assert "error" not in res, res
    return res["result"]


def diag_ok(stubs, spec):
    sig = ok(stubs.call("get_catchup", {}))["signal_id"]
    ok(stubs.call("add_hypothesis", {"rank": 2, "claim": "ledger volume is full", "test": "disk headroom",
                                     "expected_evidence": "free below floor"}))
    ok(stubs.call("add_hypothesis", {"rank": 1, "claim": "process stopped after update", "test": "unit state and catch-up",
                                     "expected_evidence": "unit inactive, slots behind"}))
    ok(stubs.call("set_hypothesis_status", {"hypothesis_id": "h2", "status": "supported", "evidence_refs": [sig]}))
    return {"hypothesis_ids": ["h1", "h2"]}


def plan_ok(stubs, spec):
    view = stubs.read_episode()
    sig = view["signals"][-1]["id"]
    r = ok(stubs.call("propose_recommendation", {
        "hypothesis_id": "h2", "action_text": "Restart the validator in an idle window",
        "skill": "restart-idle-window", "preconditions": ["no own leader slot within window", "--no-snapshot-fetch"],
        "expected_postcondition": "catch-up recovers within W samples", "evidence_refs": [sig]}))
    return {"artefact_id": r["recommendation_id"]}


def judge(result):
    def fn(stubs, spec):
        target = spec["input_view"]["under_judgement"]["id"]
        ok(stubs.call("submit_verdict", {"target_id": target, "result": result, "checks": [
            {"check": "preconditions_match_confirmed_mode", "result": "pass"},
            {"check": "least_impact", "result": "pass" if result == "PASS" else "fail", "note": "seeded"}]}))
        return {"target_id": target, "result": result}
    return fn


def report_ok(stubs, spec):
    kind = spec["kind"]
    ref = ok(stubs.call("write_incident_report", {"kind": kind, "markdown": f"# {kind} report\nSystem executed nothing."}))["ref"]
    ok(stubs.call("send_alert", {"kind": kind, "summary": "Validator behind; restart recommended."}))
    return {"report_ref": ref}


ALL_OK = {"diagnostician": diag_ok, "change_planner": plan_ok, "proposal_judge": judge("PASS"), "reporter": report_ok}


def drive(runner, stack, eid, n=12, until=None):
    for _ in range(n):
        runner.tick()
        if until and stack.rec(eid)["state"] == until:
            return


def test_primary_flow_to_resolved_with_closure(stack):
    stack.observer.set("catchup", {"slots_behind": 900, "caught_up": False})
    eid = stack.open_episode()
    runner, launcher = stack.runner(ALL_OK)
    drive(runner, stack, eid, until="awaiting_operator")
    rec = stack.rec(eid)
    assert rec["state"] == "awaiting_operator", rec["state_history"]
    assert [s["role"] for s in rec["steps"]] == ["diagnostician", "change_planner", "proposal_judge", "reporter"]
    assert all(s["outcome"] == "ok" for s in rec["steps"])
    assert set(rec["cost"]["per_role_usd"]) == {"diagnostician", "change_planner", "proposal_judge", "reporter"}
    # the judge's input was the judge view (SR-12)
    jspec = [s for s in launcher.specs if s["role"] == "proposal_judge"][0]
    assert jspec["input_view"]["view"] == "judge" and "hypotheses" not in jspec["input_view"]
    # AW-2 alert fields come from the record, not from the model
    alerts = RpcClient(stack.sock("report-broker", "system")).call("alerts_for", episode_id=eid)
    inc = [a for a in alerts if a["kind"] == "incident"][0]
    assert inc["fault_class"] == "FC-1" and inc["judge_verdict"].startswith("PASS on r1")
    assert inc["top_hypothesis"].startswith("rank 1: process stopped")
    # operator acts outside the system; verifier confirms recovery
    stack.observer.set("catchup", {"slots_behind": 0, "caught_up": True})
    stack.observer.set("host_metrics", {"unit_active": True, "min_free_pct": 40})
    from valops.verifier.verifier import Verifier
    v = Verifier(stack.verify, RpcClient(stack.sock("observer-broker", "system")),
                 RpcClient(stack.sock("report-broker", "system")), stack.registry)
    for _ in range(6):
        v.tick()
    assert stack.rec(eid)["state"] == "resolved"
    runner.tick()
    rec = stack.rec(eid)
    assert rec["state"] == "resolved" and [r["kind"] for r in rec["reports"]] == ["incident", "closure"]


def test_missing_artefact_retries_then_hands_off(stack):
    eid = stack.open_episode()
    runner, _ = stack.runner({**ALL_OK, "diagnostician": lambda s, sp: None})  # prose only, no artefact
    drive(runner, stack, eid)
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off"
    assert len([s for s in rec["steps"] if s["outcome"] == "failed"]) == 2  # P-08 = 1 retry
    assert "missing artefact" in rec["state_history"][-1]["reason"]


def test_missing_verdict_is_never_pass(stack):
    stack.observer.set("catchup", {"slots_behind": 900})
    eid = stack.open_episode()
    runner, _ = stack.runner({**ALL_OK, "proposal_judge": lambda s, sp: {"target_id": "r1", "result": "PASS"}})
    drive(runner, stack, eid)
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off" and not rec["reports"]


def test_structured_output_disagreeing_with_store_is_a_step_failure(stack):
    stack.observer.set("catchup", {"slots_behind": 900})
    eid = stack.open_episode()

    def lying_judge(stubs, spec):
        judge("FAIL")(stubs, spec)
        return {"target_id": "r1", "result": "PASS"}  # claims PASS; the store says FAIL
    runner, _ = stack.runner({**ALL_OK, "proposal_judge": lying_judge})
    drive(runner, stack, eid)
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off"
    assert any("disagrees" in (s.get("reason") or "") for s in rec["steps"])


def test_judge_fail_retries_then_hands_off_with_reasons(stack):
    stack.observer.set("catchup", {"slots_behind": 900})
    eid = stack.open_episode()
    runner, _ = stack.runner({**ALL_OK, "proposal_judge": judge("FAIL")})
    drive(runner, stack, eid, n=15)
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off"
    assert len(rec["verdicts"]) == 2 and "least_impact" in rec["state_history"][-1]["reason"]
    assert len(rec["recommendations"]) == 2  # FAIL returned to the planner once (P-09 = 1)


def test_step_timeout_counts_as_failure(stack):
    eid = stack.open_episode()
    runner, _ = stack.runner({**ALL_OK, "diagnostician": lambda s, sp: "timeout"})
    drive(runner, stack, eid)
    assert stack.rec(eid)["state"] == "handed_off"


def test_tokens_revoked_after_step(stack):
    stack.observer.set("catchup", {"slots_behind": 900})
    eid = stack.open_episode()
    runner, launcher = stack.runner(ALL_OK)
    runner.tick(); runner.tick()  # open->diagnosing, diagnostician step
    spec = launcher.specs[0]
    from valops.common.rpc import RpcError
    with pytest.raises(RpcError) as e:
        RpcClient(stack.sock("episode-broker", "worker")).call("read_episode", token=spec["token"], episode_id=eid)
    assert e.value.code == "token_revoked"


def test_no_llm_step_when_anchor_lag_exceeds_p19(stack):
    eid = stack.open_episode()
    stack.seq.last_anchor_ts = 0  # anchor lag far above P-19
    runner, launcher = stack.runner(ALL_OK)
    drive(runner, stack, eid, n=3)
    assert stack.rec(eid)["state"] == "open" and not launcher.specs
    assert any("anchor lag" in r for r in runner.last_preflight.no_llm)


def test_bundle_tamper_forces_observe_only(stack):
    import os
    eid = stack.open_episode()
    d = stack.bundles_dir / stack.bundle_id
    os.chmod(d, 0o755)
    (d / "extra.md").write_text("x")
    runner, launcher = stack.runner(ALL_OK)
    drive(runner, stack, eid, n=3)
    assert not launcher.specs and runner.last_preflight.observe_only
    assert "fails verification" in (runner.d.flag.get() or "")


def test_revoked_bundle_hands_off_in_flight_episode(stack):
    eid = stack.open_episode()
    stack.registry.revoke(stack.bundle_id, reason="test", by="test")
    runner, _ = stack.runner(ALL_OK)
    runner.tick()
    rec = stack.rec(eid)
    assert rec["state"] == "handed_off" and "revoked" in rec["state_history"][-1]["reason"]
