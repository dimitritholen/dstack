#!/usr/bin/env python3
"""Append a single progress event to a duo-plan run's events.jsonl.

Safe for concurrent writers: each event is one JSON line written with O_APPEND,
so the Claude subagent, the codex watcher, and the orchestrator can all log
without locking or read-modify-write races.

Usage:
  python3 log_event.py --run-dir DIR --agent claude --type step --text "Analyseert auth-module"

Types:
  step   - a milestone; the dashboard shows the latest step as "current activity"
  log    - informational line in the event feed
  status - lifecycle change; text must be one of: working, done, error
  error  - something went wrong (also shown red in the feed)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--agent", required=True, choices=["claude", "codex", "system"])
    p.add_argument("--type", required=True, choices=["step", "log", "status", "error"])
    p.add_argument("--text", required=True)
    args = p.parse_args()

    if args.type == "status" and args.text not in ("working", "done", "error"):
        print("ERROR status text must be working|done|error", file=sys.stderr)
        return 1

    event = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "agent": args.agent,
        "type": args.type,
        "text": args.text,
    }
    path = os.path.join(args.run_dir, "events.jsonl")
    line = json.dumps(event, ensure_ascii=False) + "\n"
    # O_APPEND keeps concurrent single-line writes intact on local filesystems.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
