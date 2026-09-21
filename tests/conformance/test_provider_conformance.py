"""PC-1 … PC-9 per configuration (plan §5.12.3, HLD §10.1). These run ONLY on the deployed
topology with the pinned runtime inside the real rootfs (W1, W1-O, W1-G, W24) and decide PA
and D20. Locally, the checks that need no runtime are exercised; the rest are skipped with
the exact admission question they answer."""
import os

import pytest

from valops.common.tools import TOOLS_BY_ROLE
from valops.worker.adapters.antigravity_cli.launcher import NotAdmitted, run as run_agy
from valops.worker.adapters.codex_cli.config import config_toml
from valops.worker.tools.stubs import ToolStubs

REAL = os.environ.get("VALOPS_CONFORMANCE_CONFIG")


def test_pc6_mcp_server_lists_only_role_tools(tmp_path):
    import io
    import json

    from valops.worker.tools.mcp_server import serve

    spec = {"role": "proposal_judge", "tools": TOOLS_BY_ROLE["proposal_judge"], "sockets": {}, "token": "t", "episode_id": "e"}
    inp = io.StringIO("\n".join(json.dumps(x) for x in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "propose_recommendation", "arguments": {}}}]) + "\n")
    out = io.StringIO()
    serve(ToolStubs(spec), inp, out)
    resp = [json.loads(x) for x in out.getvalue().splitlines()]
    assert sorted(t["name"] for t in resp[1]["result"]["tools"]) == sorted(TOOLS_BY_ROLE["proposal_judge"])
    assert resp[2]["result"]["isError"] is True


def test_pc4_codex_config_uses_placeholder_and_broker_only():
    t = config_toml(model="m", port=18080, mcp_command=["/usr/bin/python3", "-m", "valops.worker.tools.mcp_server", "/h/s.json"])
    assert 'base_url = "http://127.0.0.1:18080/openai/v1"' in t and "api.openai.com" not in t


def test_pc4_antigravity_refused_without_verified_override():
    with pytest.raises(NotAdmitted):
        run_agy({"configuration": {"model": "m", "admission": "pending"}, "model_port": 1}, 10)


@pytest.mark.real_boundary
@pytest.mark.skipif(not REAL, reason="needs the deployed topology and pinned runtime (W1/W1-O/W1-G)")
@pytest.mark.parametrize("pc", ["PC-1 hang killed at P-11", "PC-2 each built-in tool removed or inert",
                                "PC-3 planted AGENTS.md/CLAUDE.md/GEMINI.md ignored", "PC-4 host cached login unused",
                                "PC-5 never runs unsandboxed", "PC-7 blocked update/telemetry does not fail open",
                                "PC-8 same inputs => same tool surface", "PC-9 prompt from bound bundle only"])
def test_conformance_on_real_topology(pc):  # pragma: no cover
    pytest.fail(f"{pc}: implement against the pinned runtime in W1 and record the result in docs/gates/")
