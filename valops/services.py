"""Service entry points: one per process class (deploy/ops-host/*.service runs each under
its own uid). Each ``build_*`` returns (servers, background_threads) without blocking so
tests and the development stack can compose them."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import yaml

from .audit.anchor import from_config as anchor_from_config
from .audit.client import AuditClient
from .audit.sequencer import AuditSequencer
from .brokers.alerts import from_config as sink_from_config
from .brokers.episode_broker import EpisodeBroker
from .brokers.model_broker import ModelBroker
from .brokers.observer_broker import ObserverBroker
from .brokers.report_broker import ReportBroker
from .common.crypto import Signer, Verifier
from .common.rpc import RpcClient, RpcServer
from .common.tokens import TokenGate
from .config import Config
from .controller.preflight import ObserveOnlyFlag
from .controller.runner import ControllerDeps, Runner
from .controller.spawn import BwrapLauncher
from .observer.client import ObserverClient
from .sandbox.bwrap import RootfsSpec
from .sentinel.scheduler import Sentinel
from .store.service import EpisodeStore
from .verifier.verifier import Verifier as RecoveryVerifier

log = logging.getLogger(__name__)
Built = tuple[list[RpcServer], list[threading.Thread]]


def _thread(target, *args, name: str) -> threading.Thread:
    t = threading.Thread(target=target, args=args, name=name, daemon=True)
    t.start()
    return t


def _gate(cfg: Config) -> TokenGate:
    reg = cfg.bundles()
    return TokenGate(cfg.token_verifier(), bundle_ok=reg.verify)


def build_sequencer(cfg: Config, stop: threading.Event) -> tuple[Built, AuditSequencer]:
    k = cfg["keys"]
    minutes = float(cfg.get("anchor_interval_min", 15))  # = P-18 from the register
    seq = AuditSequencer(cfg.state / "audit" / "chain.jsonl", cfg.state / "audit" / "payloads",
                         Signer.load(k["chain_private"]), k["chain_key_id"], anchor_from_config(cfg["anchor"]),
                         minutes * 60, Verifier.load(k["daemon_public"]) if k.get("daemon_public") else None)
    submitters = {p: cfg.uids[p] for p in ("controller", "verifier", "store", "episode_broker", "observer_broker",
                                           "report_broker", "model_broker")}
    srv = RpcServer(seq.endpoints(str(cfg.paths.run / "audit"), submitters)).start()
    try:
        seq.anchor_now()  # anchor at start so the lag clock begins from a confirmed anchor
    except Exception as e:  # noqa: BLE001
        log.error("initial anchor failed: %s", e)
    return ([srv], [_thread(seq.anchor_loop, name="anchor")]), seq


def build_store(cfg: Config, stop: threading.Event) -> tuple[Built, EpisodeStore]:
    (cfg.state / "store").mkdir(parents=True, exist_ok=True)
    store = EpisodeStore(cfg.state / "store" / "episodes.sqlite", cfg.bundles(), _gate(cfg),
                         AuditClient(cfg.paths.audit("store"), buffer=True))
    srv = RpcServer(store.endpoints(str(cfg.paths.run / "store"), cfg.uids)).start()
    return ([srv], []), store


def build_episode_broker(cfg: Config, stop: threading.Event) -> Built:
    b = EpisodeBroker(_gate(cfg), AuditClient(cfg.paths.audit("episode_broker")), cfg.paths.store("agent"), cfg.bundles())
    srv = RpcServer(b.endpoints(str(cfg.paths.run / "episode-broker"), cfg.uids["worker"], cfg.uids["controller"])).start()
    return [srv], []


def build_observer_broker(cfg: Config, stop: threading.Event) -> Built:
    o = cfg["observer"]
    client = ObserverClient(o["url"], client_cert=o.get("client_cert"), client_key=o.get("client_key"), ca=o.get("ca"),
                            timeout=float(o.get("timeout_s", 30)))
    b = ObserverBroker(_gate(cfg), AuditClient(cfg.paths.audit("observer_broker"), buffer=True), client,
                       cfg.paths.store("observe"), cfg.bundles())
    srv = RpcServer(b.endpoints(str(cfg.paths.run / "observer-broker"), cfg.uids["worker"],
                                cfg.uids["controller"] | cfg.uids["verifier"], cfg.uids["controller"])).start()
    t = _thread(b.checkpoint_loop, float(cfg.get("checkpoint_interval_s", 60)), stop, name="daemon-checkpoints")
    return [srv], [t]


def build_report_broker(cfg: Config, stop: threading.Event) -> Built:
    b = ReportBroker(_gate(cfg), AuditClient(cfg.paths.audit("report_broker"), buffer=True), cfg.paths.store("agent-report"),
                     cfg.bundles(), sink_from_config(cfg["alerts"]), cfg.state / "reports",
                     ack_window_s=float(cfg.get("ack_window_min", 15)) * 60, development=cfg.development)
    srv = RpcServer(b.endpoints(str(cfg.paths.run / "report-broker"), cfg.uids["worker"],
                                cfg.uids["controller"] | cfg.uids["verifier"], cfg.uids["controller"],
                                cfg.uids["operator"])).start()
    return [srv], [_thread(b.escalate_loop, stop, name="aw3-escalation")]


def build_model_broker(cfg: Config, stop: threading.Event) -> Built:
    mb = cfg["model_broker"]
    keys = {p: Path(f).read_text().strip() for p, f in (mb.get("keys") or {}).items()}
    approved: set[str] = set()
    if mb.get("approvals_file") and Path(mb["approvals_file"]).exists():
        doc = yaml.safe_load(Path(mb["approvals_file"]).read_text()) or {}
        approved = {p for p, a in (doc.get("providers") or {}).items() if a and a.get("approved") is True and a.get("record")}
    broker = ModelBroker(cfg.paths.model_sessions, cfg.bundles(), keys, approved,
                         AuditClient(cfg.paths.audit("model_broker")), cfg.uids["worker"],
                         allow_insecure_upstream=bool(mb.get("allow_insecure_upstream_for_tests")) and cfg.development,
                         development=cfg.development)
    srv = RpcServer([broker.admin_endpoint(cfg.paths.broker("model-broker", "admin"), cfg.uids["controller"])]).start()
    return [srv], []


def controller_deps(cfg: Config) -> ControllerDeps:
    sb = cfg["sandbox"]
    rootfs = {a: RootfsSpec(path=p) for a, p in (sb.get("rootfs") or {}).items()}
    if cfg.development and sb.get("host_ro_dev"):
        pkg = str(Path(__file__).resolve().parent)
        for a in ("native", "claude_sdk", "codex_cli", "antigravity_cli"):
            rootfs.setdefault(a, RootfsSpec(host_ro=True, extra_ro={pkg: "/opt/valops/valops", **(sb.get("extra_ro") or {})}))
    launcher = BwrapLauncher(rootfs, worker_uid=sb.get("worker_uid"), worker_gid=sb.get("worker_gid"),
                             scratch_mb=sb.get("scratch_mb"), python_path=sb.get("python_path", "/opt/valops"))
    steps = cfg.state / "steps"
    steps.mkdir(parents=True, exist_ok=True)
    p = cfg.paths
    return ControllerDeps(
        store=RpcClient(p.store("control")), audit=AuditClient(p.audit("controller")), bundles=cfg.bundles(),
        token_signer=Signer.load(cfg["keys"]["token_private"]), report_sys=RpcClient(p.broker("report-broker", "system")),
        admins={"episode_broker": RpcClient(p.broker("episode-broker", "admin")),
                "observer_broker": RpcClient(p.broker("observer-broker", "admin")),
                "report_broker": RpcClient(p.broker("report-broker", "admin"))},
        model_admin=RpcClient(p.broker("model-broker", "admin")), launcher=launcher,
        worker_sockets={"episode": p.broker("episode-broker", "worker"), "observer": p.broker("observer-broker", "worker"),
                        "report": p.broker("report-broker", "worker")},
        steps_dir=steps, flag=ObserveOnlyFlag(cfg.state / "observe_only.json"),
        chain_path=cfg.state / "audit" / "chain.jsonl", anchor_store=anchor_from_config(cfg["anchor"]),
        anchor_keys=cfg.anchor_keys(), development=cfg.development)


def build_controller(cfg: Config, stop: threading.Event) -> tuple[Built, Runner, Sentinel]:
    deps = controller_deps(cfg)
    runner = Runner(deps)
    p = cfg.paths
    sentinel = Sentinel(RpcClient(p.store("control")), RpcClient(p.broker("observer-broker", "system")), deps.report_sys,
                        AuditClient(p.audit("controller"), buffer=True), deps.bundles,
                        watchtower_heartbeat=cfg.get("watchtower_heartbeat"))
    threads = [_thread(sentinel.loop, stop, name="sentinel"),
               _thread(runner.loop, stop, float(cfg.get("controller_interval_s", 5)), name="runner")]
    return ([], threads), runner, sentinel


def build_verifier(cfg: Config, stop: threading.Event) -> tuple[Built, RecoveryVerifier]:
    p = cfg.paths
    v = RecoveryVerifier(RpcClient(p.store("verify")), RpcClient(p.broker("observer-broker", "system")),
                         RpcClient(p.broker("report-broker", "system")), cfg.bundles())
    return ([], [_thread(v.loop, stop, float(cfg.get("verifier_interval_s", 15)), name="verifier")]), v


BUILDERS = {
    "sequencer": lambda c, s: build_sequencer(c, s)[0],
    "store": lambda c, s: build_store(c, s)[0],
    "episode-broker": build_episode_broker,
    "observer-broker": build_observer_broker,
    "report-broker": build_report_broker,
    "model-broker": build_model_broker,
    "controller": lambda c, s: build_controller(c, s)[0],
    "verifier": lambda c, s: build_verifier(c, s)[0],
}
ORDER = ("sequencer", "store", "episode-broker", "observer-broker", "report-broker", "model-broker", "verifier", "controller")


def serve(cfg: Config, names: list[str]) -> None:
    stop = threading.Event()
    servers: list[RpcServer] = []
    for n in names:
        srvs, _ = BUILDERS[n](cfg, stop)
        servers += srvs
        log.info("started %s", n)
    try:
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for s in servers:
            s.stop()
