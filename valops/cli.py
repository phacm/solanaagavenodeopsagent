"""`valops` command line.

  valops keygen DIR                              generate dev keys (production: D14 ceremony)
  valops bundle build|activate|revoke|rollback|verify|list ...
  valops chain verify --config C                 walk the chain and compare with anchors
  valops serve --config C NAME...                run one or more ops-host process classes
  valops observerd --config C                    validator-host observer daemon
  valops alerts|ack --config C                   operator: list / acknowledge alerts (AW-3)
  valops observe-only clear --config C           operator: after the RB-3/RB-10 exit condition
  valops check-write-path [ROOT]                 static write-path-absence check (§10.2)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml


def _cfg(args):
    from .config import Config

    return Config.load(args.config)


def cmd_keygen(args) -> int:
    from .common.crypto import Signer

    out = Path(args.dir)
    for name in ("token", "chain", "bundle", "daemon"):
        s = Signer.generate()
        s.save(out / f"{name}.pem")
        s.verifier.save(out / f"{name}.pub.pem")
    print(f"wrote token/chain/bundle/daemon keys to {out} (DEVELOPMENT ONLY; D14 governs production custody)")
    return 0


def cmd_bundle(args) -> int:
    from .bundle.builder import build
    from .common.crypto import Signer

    if args.action == "build":
        with open(args.register) as f:
            register = yaml.safe_load(f)
        signer = Signer.load(args.key) if args.key else None
        bid = build(Path(args.src), register, Path(args.out), signer=signer, key_id=args.key_id,
                    overlay=Path(args.overlay) if args.overlay else None)
        print(bid)
        return 0
    reg = _cfg(args).bundles()
    if args.action == "verify":
        reason = reg.verify(args.id)
        print(reason or "ok")
        return 1 if reason else 0
    if args.action == "activate":
        reg.activate(args.id, by=args.by)
    elif args.action == "revoke":
        reg.revoke(args.id, reason=args.reason, by=args.by)
    elif args.action == "rollback":
        print(reg.rollback(by=args.by))
    elif args.action == "list":
        print(json.dumps({"active": reg.active(), "revoked": sorted(reg.revoked()), "history": reg.history()}, indent=1))
    return 0


def cmd_chain(args) -> int:
    from .audit.anchor import from_config
    from .audit.sequencer import verify_chain

    cfg = _cfg(args)
    res = verify_chain(cfg.state / "audit" / "chain.jsonl", from_config(cfg["anchor"]).list(), cfg.anchor_keys())
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


def cmd_serve(args) -> int:
    from .services import ORDER, serve

    names = list(ORDER) if args.names == ["all"] else args.names
    serve(_cfg(args), names)
    return 0


def cmd_observerd(args) -> int:
    from .common.crypto import Signer
    from .observer.chain import LocalChain
    from .observer.daemon import ObserverDaemon, serve
    from .observer.table import load_table

    with open(args.config) as f:
        c = yaml.safe_load(f)
    table = load_table(c["command_table"])  # OD-3: refuses to start on a non-read-only table
    d = ObserverDaemon(table, c["local"], LocalChain(c["chain"]["path"], Signer.load(c["chain"]["key"])),
                       rate_per_min=int(c["rate_per_min"]), breaker_threshold_ms=float(c["breaker_threshold_ms"]))
    t = c.get("tls") or {}
    if not t and not c.get("development"):
        print("refusing to serve without mTLS outside development", file=sys.stderr)
        return 2
    httpd = serve(d, c["listen"]["host"], int(c["listen"]["port"]), certfile=t.get("cert"), keyfile=t.get("key"),
                  client_ca=t.get("client_ca"), expected_client_cn=t.get("expected_client_cn"))
    httpd.serve_forever()
    return 0


def cmd_alerts(args) -> int:
    from .common.rpc import RpcClient

    c = RpcClient(_cfg(args).paths.broker("report-broker", "operator"))
    if args.action == "ack":
        print(c.call("ack", alert_id=args.alert_id))
    else:
        for a in c.call("list_alerts", limit=args.limit):
            print(f"{a['alert_id'][:12]} {a['severity']:8} acked={a.get('acked')} {a.get('title')}")
    return 0


def cmd_observe_only(args) -> int:
    from .controller.preflight import ObserveOnlyFlag

    flag = ObserveOnlyFlag(_cfg(args).state / "observe_only.json")
    print(f"clearing observe-only (was: {flag.get()})")
    flag.clear()
    return 0


def cmd_check_write_path(args) -> int:
    from .writepath import check

    problems = check(Path(args.root))
    for p in problems:
        print(p)
    print("write-path absence: " + ("FAIL" if problems else "ok"))
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="valops")
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen")
    k.add_argument("dir")
    k.set_defaults(fn=cmd_keygen)

    b = sub.add_parser("bundle")
    b.add_argument("action", choices=["build", "activate", "revoke", "rollback", "verify", "list"])
    b.add_argument("id", nargs="?")
    b.add_argument("--config")
    b.add_argument("--src", default="policy/bundle-src")
    b.add_argument("--register", default="docs/registers/parameters.yaml")
    b.add_argument("--out")
    b.add_argument("--key")
    b.add_argument("--key-id", default="bundle-key-1")
    b.add_argument("--overlay", help="development overlay dir copied over --src (no gate weight)")
    b.add_argument("--reason", default="")
    b.add_argument("--by", default="operator")
    b.set_defaults(fn=cmd_bundle)

    c = sub.add_parser("chain")
    c.add_argument("action", choices=["verify"])
    c.add_argument("--config", required=True)
    c.set_defaults(fn=cmd_chain)

    s = sub.add_parser("serve")
    s.add_argument("--config", required=True)
    s.add_argument("names", nargs="+")
    s.set_defaults(fn=cmd_serve)

    o = sub.add_parser("observerd")
    o.add_argument("--config", required=True)
    o.set_defaults(fn=cmd_observerd)

    for name in ("alerts", "ack"):
        a = sub.add_parser(name)
        a.add_argument("--config", required=True)
        if name == "ack":
            a.add_argument("alert_id")
        a.add_argument("--limit", type=int, default=50)
        a.set_defaults(fn=cmd_alerts, action=name)

    oo = sub.add_parser("observe-only")
    oo.add_argument("action", choices=["clear"])
    oo.add_argument("--config", required=True)
    oo.set_defaults(fn=cmd_observe_only)

    w = sub.add_parser("check-write-path")
    w.add_argument("root", nargs="?", default=".")
    w.set_defaults(fn=cmd_check_write_path)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
