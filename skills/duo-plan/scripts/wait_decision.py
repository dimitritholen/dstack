#!/usr/bin/env python3
"""Block until the user has made a decision in the duo-plan dashboard.

The dashboard server is the only writer of decisions.json; this script polls it
and exits as soon as the requested input is present, so the orchestrator can
run it as a BACKGROUND Bash task and get woken by the completion notification
instead of polling itself.

Modes:
  --for conflicts --ids c1,c2   exit when ALL listed conflict ids have a decision
  --for approval [--min-count N] exit when the approvals list has >= N entries
                                 (default: 1). Use N = previous count + 1 when
                                 waiting for a NEW verdict after a revision round.

Output on stdout (last line, machine-readable):
  DECISIONS <json>   for conflicts mode: {"c1": {...}, "c2": {...}}
  APPROVAL <json>    for approval mode: the newest approval entry
Exit codes: 0 = got input, 3 = timeout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def read_decisions(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--for", dest="mode", required=True, choices=["conflicts", "approval"])
    p.add_argument("--ids", default="", help="comma-separated conflict ids (conflicts mode)")
    p.add_argument("--min-count", type=int, default=1, help="approvals needed (approval mode)")
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--poll", type=float, default=1.0)
    args = p.parse_args()

    path = os.path.join(args.run_dir, "decisions.json")
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    if args.mode == "conflicts" and not ids:
        print("ERROR conflicts mode requires --ids", file=sys.stderr)
        return 1

    start = time.time()
    while True:
        data = read_decisions(path)
        if args.mode == "conflicts":
            decisions = data.get("decisions", {})
            if all(i in decisions for i in ids):
                picked = {i: decisions[i] for i in ids}
                print("DECISIONS " + json.dumps(picked, ensure_ascii=False))
                return 0
        else:
            approvals = data.get("approvals", [])
            if len(approvals) >= args.min_count:
                print("APPROVAL " + json.dumps(approvals[-1], ensure_ascii=False))
                return 0

        if time.time() - start > args.timeout:
            print(f"ERROR timeout after {args.timeout}s", file=sys.stderr)
            return 3
        time.sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
