"""Test stack: real services over real Unix sockets in a temp dir, single uid.

These runs exercise the code paths deterministically; per HLD §10.1 they carry NO G1
weight (single uid, file anchor store, fake observer and fake provider upstream). The
`real_boundary` marker is reserved for runs on the deployed topology.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from valops.audit.anchor import FileAnchorStore
from valops.audit.client import AuditClient
from valops.audit.sequencer import AuditSequencer
from valops.brokers.alerts import FileSink
from valops.brokers.episode_broker import EpisodeBroker
from valops.brokers.model_broker import ModelBroker
from valops.brokers.observer_broker import ObserverBroker
from valops.brokers.report_broker import ReportBroker
from valops.bundle.builder import build
from valops.bundle.registry import BundleRegistry, TrustedKey
from valops.common.crypto import Signer
from valops.common.rpc import RpcClient, RpcServer
from valops.common.tokens import TokenGate, mint
from valops.controller.preflight import ObserveOnlyFlag
from valops.controller.runner import ControllerDeps, Runner
from valops.observer.client import ObserverUnreachable
from valops.store.service import EpisodeStore

ROOT = Path(__file__).resolve().parent.parent
UID = os.getuid()
CLASSES = ("controller", "worker", "verifier", "episode_broker", "observer_broker", "report_broker", "model_broker",
           "audit_sequencer", "store", "operator")


def dev_register() -> dict:
    return yaml.safe_load((ROOT / "policy/dev/parameters.dev.yaml").read_text())


def build_bundle(out: Path, signer: Signer, *, mutate=None, register=None) -> str:
    src = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "policy/bundle-src", src, dirs_exist_ok=True)
    shutil.copytree(ROOT / "policy/dev/overlay", src, dirs_exist_ok=True)
    if mutate:
        mutate(src)
    try:
        return build(src, register or dev_register(), out, signer=signer, key_id="k1")
    finally:
        shutil.rmtree(src)


class FakeObserver:
    """Scripted stand-in for the mTLS daemon client (unit-level; no G1 weight)."""

    def __init__(self):
        self.reachable = True
        self.results: dict[str, dict] = {}
        self.calls: list[str] = []

    def set(self, cid: str, structured: dict, status: str = "ok") -> None:
        self.results[cid] = {"status": status, "structured": {"parsed": True, **structured}}

    def observe(self, cid, args=None):
        from valops.common.canonical import now

        self.calls.append(cid)
        if not self.reachable:
            raise ObserverUnreachable("connection refused")
        r = self.results.get(cid, {"status": "unavailable", "structured": {"parsed": False}})
        return ({"command_id": cid, "request_id": "r", "collected_at": now(), "output": "", "truncated": False,
                 "flags": [], "audit_ref": "daemon:1", **r}, 3.0)

    def health(self):
        if not self.reachable:
            raise ObserverUnreachable("connection refused")
        return {"ok": True, "breaker": {"open": False, "trips": 0}}, 2.0

    def checkpoint(self, since):
        raise ObserverUnreachable("not in tests")


class FakeProvider:
    """Records what the model broker forwards upstream."""

    def __init__(self):
        self.requests: list[dict] = []
        self.response = {"id": "msg", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "ok"}],
                         "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 20}}
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):  # noqa: N802
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                       "body": json.loads(body)})
                data = json.dumps(outer.response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"


class FakeLauncher:
    """Replaces the bwrap launcher in control-plane tests: runs a scripted 'worker' that
    calls the real brokers with the real token from the generated step.json."""

    def __init__(self, stack, behaviours: dict):
        self.stack = stack
        self.behaviours = behaviours
        self.specs: list[dict] = []

    def preflight(self):
        return None

    def run(self, *, adapter, home, bundle_dir, sockets, timeout_s):
        from valops.controller.spawn import LaunchResult
        from valops.worker.tools.stubs import ToolStubs

        spec = json.loads((home / "step.json").read_text())
        self.specs.append(spec)
        spec["sockets"] = {k: v for k, v in sockets.items()}
        stubs = ToolStubs(spec)
        fn = self.behaviours.get(spec["role"])
        out = fn(stubs, spec) if fn else None
        if out == "timeout":
            return LaunchResult(None, True, None, b"")
        return LaunchResult(0, False, out, b"worker stderr (never parsed)")


class Stack:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.run = Path(tempfile.mkdtemp(prefix="vo-", dir="/tmp"))  # short path: AF_UNIX limit
        self.uids = {c: {UID} for c in CLASSES}
        self.token_signer, self.bundle_signer, self.chain_signer = Signer.generate(), Signer.generate(), Signer.generate()
        self.bundles_dir = tmp / "bundles"
        self.bundle_id = build_bundle(self.bundles_dir, self.bundle_signer)
        self.registry = self.make_registry()
        self.registry.activate(self.bundle_id, by="test")
        self.anchor = FileAnchorStore(tmp / "anchors.jsonl")
        self.servers: list[RpcServer] = []
        self.stop = threading.Event()

        self.seq = AuditSequencer(tmp / "chain.jsonl", tmp / "payloads", self.chain_signer, "c1", self.anchor, 3600)
        self._serve(self.seq.endpoints(str(self.run / "audit"), {p: {UID} for p in (
            "controller", "verifier", "store", "episode_broker", "observer_broker", "report_broker", "model_broker")}))
        self.seq.anchor_now()

        self.gate = TokenGate(self.token_signer.verifier, bundle_ok=self.registry.verify)
        self.store = EpisodeStore(tmp / "store.sqlite", self.registry, self.gate, AuditClient(self.sock("audit", "store"), buffer=True))
        self._serve(self.store.endpoints(str(self.run / "store"), self.uids))

        self.episode_broker = EpisodeBroker(TokenGate(self.token_signer.verifier, self.registry.verify),
                                            AuditClient(self.sock("audit", "episode_broker")), self.sock("store", "agent"), self.registry)
        self._serve(self.episode_broker.endpoints(str(self.run / "episode-broker"), {UID}, {UID}))

        self.observer = FakeObserver()
        self.observer_broker = ObserverBroker(TokenGate(self.token_signer.verifier, self.registry.verify),
                                              AuditClient(self.sock("audit", "observer_broker")), self.observer,
                                              self.sock("store", "observe"), self.registry)
        self._serve(self.observer_broker.endpoints(str(self.run / "observer-broker"), {UID}, {UID}, {UID}))

        self.alert_path = tmp / "alerts.jsonl"
        self.report_broker = ReportBroker(TokenGate(self.token_signer.verifier, self.registry.verify),
                                          AuditClient(self.sock("audit", "report_broker")), self.sock("store", "agent-report"),
                                          self.registry, FileSink(str(self.alert_path)), tmp / "reports", ack_window_s=900,
                                          development=True)
        self._serve(self.report_broker.endpoints(str(self.run / "report-broker"), {UID}, {UID}, {UID}, {UID}))

        self.provider = FakeProvider()
        self._patch_endpoint()
        self.model_broker = ModelBroker(self.run / "mb", self.registry, {"anthropic": "sk-real-key"}, {"anthropic"},
                                        AuditClient(self.sock("audit", "model_broker")), {UID},
                                        allow_insecure_upstream=True, development=True)
        self._serve([self.model_broker.admin_endpoint(str(self.run / "model-broker" / "admin.sock"), {UID})])

        self.control = RpcClient(self.sock("store", "control"))
        self.verify = RpcClient(self.sock("store", "verify"))
        self.agent = RpcClient(self.sock("store", "agent"))

    def _patch_endpoint(self):
        """Point the active bundle's anthropic endpoint at the fake provider by building a
        second bundle (bundles are immutable) and activating it."""
        def mutate(src: Path):
            p = yaml.safe_load((src / "providers.yaml").read_text())
            p["endpoints"]["anthropic"] = self.provider.url
            (src / "providers.yaml").write_text(yaml.safe_dump(p))
        self.bundle_id = build_bundle(self.bundles_dir, self.bundle_signer, mutate=mutate)
        self.registry.activate(self.bundle_id, by="test")

    def make_registry(self) -> BundleRegistry:
        return BundleRegistry(self.bundles_dir, {"k1": TrustedKey("k1", self.bundle_signer.verifier, "active")})

    def sock(self, group: str, name: str) -> str:
        return str(self.run / group / f"{name}.sock")

    def _serve(self, eps) -> None:
        self.servers.append(RpcServer(eps).start())

    # --- helpers ---------------------------------------------------------------------
    def open_episode(self, check="delinquency", cls="validator_health", mode="tower", signals=("catchup",)) -> str:
        import uuid

        r = self.control.call("open_episode", **{"class": cls, "trigger": {"source": "sentinel", "check": check, "severity": "high"},
                                                 "validator_id": "dev-validator", "bundle_id": self.bundle_id,
                                                 "consensus_mode": mode, "idem_key": uuid.uuid4().hex})
        eid = r["episode_id"]
        for cid in signals:
            self.control.call("append_signal", episode_id=eid, snapshot={"command_id": cid, "status": "ok",
                                                                         "structured": {"parsed": True, "slots_behind": 900}},
                              idem_key=uuid.uuid4().hex)
        return eid

    def rec(self, eid: str) -> dict:
        return self.control.call("read_episode", episode_id=eid, view="record")

    def to_state(self, eid: str, *states: str) -> None:
        for s in states:
            r = self.rec(eid)
            self.control.call("set_state", episode_id=eid, state=s, expected_revision=r["revision"])

    def token(self, eid: str, role: str, session: str = "sess-1", ttl: float = 300, bundle_id: str | None = None) -> str:
        return mint(self.token_signer, episode_id=eid, role=role, session_id=session, bundle_id=bundle_id or self.bundle_id, ttl_s=ttl)

    def runner(self, behaviours: dict) -> tuple[Runner, FakeLauncher]:
        launcher = FakeLauncher(self, behaviours)
        steps = self.tmp / "steps"
        steps.mkdir(exist_ok=True)
        deps = ControllerDeps(
            store=self.control, audit=AuditClient(self.sock("audit", "controller")), bundles=self.registry,
            token_signer=self.token_signer, report_sys=RpcClient(self.sock("report-broker", "system")),
            admins={"episode_broker": RpcClient(self.sock("episode-broker", "admin")),
                    "observer_broker": RpcClient(self.sock("observer-broker", "admin")),
                    "report_broker": RpcClient(self.sock("report-broker", "admin"))},
            model_admin=RpcClient(str(self.run / "model-broker" / "admin.sock")), launcher=launcher,
            worker_sockets={"episode": self.sock("episode-broker", "worker"), "observer": self.sock("observer-broker", "worker"),
                            "report": self.sock("report-broker", "worker")},
            steps_dir=steps, flag=ObserveOnlyFlag(self.tmp / "observe_only.json"),
            chain_path=self.tmp / "chain.jsonl", anchor_store=self.anchor, anchor_keys={"c1": self.chain_signer.verifier},
            development=True)
        return Runner(deps), launcher

    def close(self) -> None:
        for s in self.servers:
            s.stop()
        self.provider.httpd.shutdown()
        shutil.rmtree(self.run, ignore_errors=True)


@pytest.fixture
def stack(tmp_path):
    s = Stack(tmp_path)
    yield s
    s.close()
