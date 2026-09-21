"""§10.1 Process topology on the LOCAL bubblewrap backend. Real sandbox, single uid:
useful evidence during development; G1 requires the deployed uids (real_boundary)."""
import os
import subprocess
import sys

import pytest

from valops.sandbox import bwrap as B

pytestmark = pytest.mark.sandbox
if not B.available()[0]:
    pytest.skip("bubblewrap backend unavailable", allow_module_level=True)

PROBE = r'''
import os, socket, sys
res = {}
try:
    open("/home/valops/x", "w"); res["write_home"] = "WROTE"
except OSError: res["write_home"] = "blocked"
try:
    open("/tmp/x", "w"); res["write_tmp"] = "WROTE"
except OSError: res["write_tmp"] = "blocked"
try:
    s = socket.create_connection(("1.1.1.1", 443), timeout=2); res["net"] = "CONNECTED"
except OSError: res["net"] = "blocked"
res["secret_env"] = [k for k in os.environ if "KEY" in k and "PLACEHOLDER" not in k]
res["home_listing"] = sorted(os.listdir("/home/valops"))
res["can_see_host_home"] = os.path.exists("/root") and bool(os.listdir("/root")) if os.access("/root", os.R_OK) else False
print(res)
'''


def _run(tmp_path, scratch=0):
    home = tmp_path / "home"
    home.mkdir()
    (home / "step.json").write_text("{}")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    spec = B.SandboxSpec(rootfs=B.RootfsSpec(host_ro=True), home=str(home), bundle=str(bundle), sockets={},
                         scratch_tmpfs_mb=scratch, env={})
    argv = B.build_argv(spec, [sys.executable if sys.executable.startswith("/usr") else "/usr/bin/python3", "-c", PROBE])
    env = {"ANTHROPIC_API_KEY": "host-secret"}  # present in the parent; clearenv must drop it
    out = subprocess.run(argv, capture_output=True, text=True, timeout=30, env={**os.environ, **env})
    assert out.returncode == 0, out.stderr
    return eval(out.stdout.strip())  # noqa: S307 - our own probe output


def test_worker_cannot_write_or_reach_network_or_see_secrets(tmp_path):
    r = _run(tmp_path)
    assert r["write_home"] == "blocked"
    assert r["write_tmp"] == "blocked"
    assert r["net"] == "blocked"
    assert r["secret_env"] == []
    assert r["home_listing"] == ["step.json"]


def test_scratch_tmpfs_is_private_and_bounded(tmp_path):
    r = _run(tmp_path, scratch=8)
    assert r["write_tmp"] == "WROTE" and r["write_home"] == "blocked"


def test_backend_unavailable_refuses_to_start(monkeypatch, tmp_path):
    from valops.controller.spawn import BwrapLauncher

    monkeypatch.setattr(B.shutil, "which", lambda name: None)
    launcher = BwrapLauncher({"native": B.RootfsSpec(host_ro=True)})
    assert launcher.preflight() is not None
    with pytest.raises(B.SandboxUnavailable):
        launcher.run(adapter="native", home=tmp_path, bundle_dir=tmp_path, sockets={}, timeout_s=5)
