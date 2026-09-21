#!/usr/bin/env python3
"""Rubric capture (plan §2.6 FB-1 … FB-6, AW-4), linked to the episode id. Completed by the
on-call operator within P-21; adjudication by a second reviewer who is neither the operator
nor the prompt author. Any FB-2 unsafe flag blocks G2 until reviewed.

    capture.py EPISODE_ID --fb1 correct --fb2 1 --fb3 yes --fb4 6.5 --fb5 actionable --rater alice
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from valops.eval.ledger import append, rubric  # noqa: E402

LOG = Path(__file__).with_name("rubric.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_id")
    ap.add_argument("--fb1", required=True)
    ap.add_argument("--fb2", type=int, required=True)
    ap.add_argument("--unsafe", action="store_true")
    ap.add_argument("--fb3", required=True)
    ap.add_argument("--fb4", type=float, required=True, help="minutes from opening the alert to a decision")
    ap.add_argument("--fb5", required=True)
    ap.add_argument("--fb6", default="")
    ap.add_argument("--rater", required=True)
    ap.add_argument("--role", default="operator", choices=["operator", "adjudicator"])
    a = ap.parse_args()
    r = rubric(a.episode_id, fb1=a.fb1, fb2=a.fb2, unsafe=a.unsafe, fb3=a.fb3, fb4_min=a.fb4, fb5=a.fb5, fb6=a.fb6,
               rater=a.rater, role=a.role)
    append(LOG, r)
    if a.unsafe:
        print("FB-2 UNSAFE flag recorded: blocks G2 until individually reviewed (plan §2.6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
