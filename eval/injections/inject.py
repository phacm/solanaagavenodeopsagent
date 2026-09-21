#!/usr/bin/env python3
"""FC-1 … FC-5 fault injection on the TESTNET validator (plan §2.6, W19).

Run by the fault injector (never the on-call operator, never the agent). The ground-truth
record is appended to the hash-chained injection log BEFORE the injection runs and before
any report is read. The injector chooses and randomises the order and includes no-fault
control windows.

    inject.py plan  FC-3                      # show what will be done
    inject.py run   FC-3 --host validator-1   # record ground truth, then execute over ssh
    inject.py control --minutes 30            # record a no-fault control window
    inject.py verify                          # verify the ground-truth log chain

These scripts change the testnet validator on purpose. They are evaluation tooling, kept
outside the `valops` package, and are not reachable from any agent tool.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from valops.eval.ledger import append, verify  # noqa: E402

LOG = Path(__file__).with_name("ground-truth.jsonl")

INJECTIONS = {
    "FC-1": {"root_cause": "validator systemd unit stopped",
             "do": "sudo systemctl stop {unit}", "undo": "sudo systemctl start {unit}"},
    "FC-2": {"root_cause": "identity balance below floor (testnet SOL moved out)",
             "do": "solana transfer --url https://api.testnet.solana.com --keypair {identity_keypair} {sink} {amount} --allow-unfunded-recipient",
             "undo": "operator refunds identity from the injector wallet"},
    "FC-3": {"root_cause": "ledger volume below headroom floor (ballast file)",
             "do": "sudo fallocate -l {ballast_size} {ledger_volume}/valops-ballast", "undo": "sudo rm -f {ledger_volume}/valops-ballast"},
    "FC-4": {"root_cause": "expected version in bundle differs from running version",
             "do": "activate the FC-4 bundle (deployment.expected_version != running) via change control",
             "undo": "re-activate the previous bundle (valops bundle rollback)"},
    "FC-5": {"root_cause": "observer daemon unreachable",
             "do": "sudo systemctl stop valops-observerd", "undo": "sudo systemctl start valops-observerd"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["plan", "run", "undo", "control", "verify"])
    ap.add_argument("fc", nargs="?")
    ap.add_argument("--host")
    ap.add_argument("--injector", default="injector")
    ap.add_argument("--minutes", type=int, default=30)
    ap.add_argument("--param", action="append", default=[], help="key=value for command placeholders")
    a = ap.parse_args()
    params = dict(p.split("=", 1) for p in a.param)
    if a.action == "verify":
        print("ok" if verify(LOG) else "CHAIN BROKEN")
        return 0
    if a.action == "control":
        append(LOG, {"injection_id": str(uuid.uuid4()), "fault_class": "control", "minutes": a.minutes, "by": a.injector})
        return 0
    spec = INJECTIONS[a.fc]
    template = spec["undo" if a.action == "undo" else "do"]
    try:
        cmd = template.format(**params)
    except KeyError as e:
        if a.action != "plan":
            print(f"missing --param {e.args[0]}=...", file=sys.stderr)
            return 2
        cmd = template
    if a.action == "plan":
        print(f"{a.fc}: {spec['root_cause']}\n  do:   {spec['do']}\n  undo: {spec['undo']}")
        return 0
    if a.action == "run":
        rec = append(LOG, {"injection_id": str(uuid.uuid4()), "fault_class": a.fc, "root_cause": spec["root_cause"],
                           "command": cmd, "host": a.host, "by": a.injector})
        print(f"ground truth recorded: {rec['injection_id']}")
    if a.host and not cmd.startswith(("activate", "re-activate", "operator")):
        return subprocess.run(["ssh", a.host, cmd]).returncode
    print(f"manual step: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
