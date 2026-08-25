#!/usr/bin/env python3
"""Tail a `codex exec` log file and translate it into duo-plan dashboard events.

Codex streams its session to stdout: reasoning summaries, the shell commands it
runs to read the repo, token counts, and finally the answer. This watcher polls
that log, classifies new lines, and appends readable events to events.jsonl via
the same O_APPEND discipline as log_event.py — so the dashboard shows live what
Codex is doing instead of a black box.

Exits when --done-file exists (codex wrote its --output-last-message) and the
log has been fully consumed, or on --max-seconds timeout.

Usage:
  python3 codex_watcher.py --run-dir DIR --log-file L --done-file OUT \
      [--label "stelt plan op"] [--poll 1.0] [--max-seconds 3600]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time

RE_TS_PREFIX = re.compile(r"^\[\d{4}-\d{2}-\d{2}T[^\]]*\]\s*(.*)$")
RE_TOKENS = re.compile(r"tokens used:?\s*([\d,\.]+)", re.IGNORECASE)
RE_EXEC = re.compile(r"^exec\s+(.*)$")
RE_RESULT = re.compile(r"(succeeded|failed|exited \-?\d+)", re.IGNORECASE)


def append_event(run_dir: str, agent: str, etype: str, text: str) -> None:
    event = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "type": etype,
        "text": text,
    }
    path = os.path.join(run_dir, "events.jsonl")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def truncate(text: str, limit: int = 160) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Classifier:
    """Stateful line classifier: after a 'thinking' marker the next non-empty
    line is a reasoning summary; after a 'codex' marker the answer starts."""

    def __init__(self, run_dir: str, label: str):
        self.run_dir = run_dir
        self.label = label
        self.expect_summary = False
        self.answer_started = False
        self.last_tokens = ""

    def feed(self, raw: str) -> None:
        line = raw.rstrip("\n")
        if not line.strip():
            return

        m = RE_TS_PREFIX.match(line)
        content = m.group(1) if m else line
        stripped = content.strip()

        if self.answer_started:
            return  # answer body streams to the log; the clean copy lands in done-file

        if self.expect_summary:
            self.expect_summary = False
            summary = truncate(stripped.strip("*# "))
            if summary:
                append_event(self.run_dir, "codex", "step", summary)
            return

        if stripped.lower() == "thinking":
            self.expect_summary = True
            return

        if stripped.lower() == "codex":
            self.answer_started = True
            append_event(self.run_dir, "codex", "step", f"Schrijft eindresultaat ({self.label})")
            return

        exec_m = RE_EXEC.match(stripped)
        if exec_m:
            append_event(self.run_dir, "codex", "log", "▶ " + truncate(exec_m.group(1), 120))
            return

        tok_m = RE_TOKENS.search(stripped)
        if tok_m:
            tokens = tok_m.group(1)
            if tokens != self.last_tokens:
                self.last_tokens = tokens
                append_event(self.run_dir, "codex", "log", f"tokens: {tokens}")
            return

        if RE_RESULT.search(stripped) and len(stripped) < 120:
            return  # command results are noise; the exec line already showed intent

        # Everything else (session header, model info, output dumps) is skipped
        # deliberately: the feed must stay readable, not mirror the raw log.


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--log-file", required=True)
    p.add_argument("--done-file", required=True)
    p.add_argument("--label", default="taak")
    p.add_argument("--poll", type=float, default=1.0)
    p.add_argument("--max-seconds", type=int, default=3600)
    args = p.parse_args()

    clf = Classifier(args.run_dir, args.label)
    append_event(args.run_dir, "codex", "status", "working")
    append_event(args.run_dir, "codex", "step", f"Codex gestart: {args.label}")

    start = time.time()
    pos = 0
    buf = ""
    done_seen_at = None

    while True:
        if os.path.exists(args.log_file):
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            if chunk:
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    clf.feed(line)

        if os.path.exists(args.done_file) and os.path.getsize(args.done_file) > 0:
            if done_seen_at is None:
                done_seen_at = time.time()
            elif time.time() - done_seen_at > 2 * args.poll:
                append_event(args.run_dir, "codex", "status", "done")
                append_event(args.run_dir, "codex", "step", f"Klaar: {args.label}")
                return 0

        if time.time() - start > args.max_seconds:
            append_event(args.run_dir, "codex", "error", f"Watcher timeout na {args.max_seconds}s")
            append_event(args.run_dir, "codex", "status", "error")
            return 2

        time.sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
