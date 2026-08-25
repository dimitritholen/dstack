#!/usr/bin/env python3
"""Live dashboard for a duo-plan run: Claude & Codex planning side-by-side.

Serves a single-page app on a free localhost port. The page polls GET /state
(composed from the run dir: control.json + events.jsonl + decisions.json +
plan files) and posts user input back:

  POST /decision  {"id": "c1", "choice": "claude"|"codex"|"custom", "note": "..."}
  POST /approval  {"approved": true|false, "note": "..."}

Single-writer discipline: this server is the ONLY writer of decisions.json;
the orchestrator owns control.json; events.jsonl is append-only for everyone.

Output protocol (consumed by the calling skill):
- On start: prints `DASHBOARD_URL <url>` on stdout, then serves forever.
- On error: prints `ERROR <message>` on stderr, exit 1.

Run in the BACKGROUND; pair with wait_decision.py to block on user input.
No external dependencies — Python stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser

LOCK = threading.Lock()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def open_browser(url: str) -> None:
    """Best-effort browser open; on macOS `open` works from background sessions."""
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    try:
        webbrowser.open(url)
    except Exception:
        pass


class RunState:
    """Reads the run dir; tolerant of half-written files (keeps last good copy)."""

    def __init__(self, run_dir: str):
        self.run_dir = run_dir
        self._last_control: dict = {}

    def control(self) -> dict:
        path = os.path.join(self.run_dir, "control.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._last_control = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return self._last_control

    def events(self, limit: int = 800) -> list:
        path = os.path.join(self.run_dir, "events.jsonl")
        events = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return events[-limit:]

    def decisions(self) -> dict:
        path = os.path.join(self.run_dir, "decisions.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"decisions": {}, "approvals": []}

    def plan_files(self, control: dict) -> dict:
        out = {}
        for key, rel in (control.get("files") or {}).items():
            path = rel if os.path.isabs(rel) else os.path.join(self.run_dir, rel)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    out[key] = f.read()
            except OSError:
                pass
        return out

    def compose(self) -> dict:
        control = self.control()
        return {
            "control": control,
            "events": self.events(),
            "decisions": self.decisions(),
            "plans": self.plan_files(control),
            "now": datetime.datetime.now().isoformat(timespec="seconds"),
        }

    def write_decision(self, payload: dict) -> None:
        path = os.path.join(self.run_dir, "decisions.json")
        with LOCK:
            data = self.decisions()
            data.setdefault("decisions", {})
            data["decisions"][payload["id"]] = {
                "choice": payload.get("choice", ""),
                "note": payload.get("note", ""),
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            self._atomic_write(path, data)

    def write_approval(self, payload: dict) -> None:
        path = os.path.join(self.run_dir, "decisions.json")
        with LOCK:
            data = self.decisions()
            data.setdefault("approvals", [])
            data["approvals"].append({
                "approved": bool(payload.get("approved")),
                "note": payload.get("note", ""),
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            })
            self._atomic_write(path, data)

    @staticmethod
    def _atomic_write(path: str, data: dict) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def make_handler(state: RunState):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence request logging
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/state":
                body = json.dumps(state.compose(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, b'{"ok":false}', "application/json")
                return
            if self.path == "/decision" and payload.get("id"):
                state.write_decision(payload)
                self._send(200, b'{"ok":true}', "application/json")
            elif self.path == "/approval":
                state.write_approval(payload)
                self._send(200, b'{"ok":true}', "application/json")
            else:
                self._send(404, b'{"ok":false}', "application/json")

    return Handler


# Design: "Richting B — Glass Depth" (Claude Design project). Glass panels op een
# gradient-pagina met drijvende kleurblobs; Sora voor koppen, Manrope voor tekst,
# JetBrains Mono voor tijden/paden. Claude = oranje, Codex = blauw. Licht/donker
# via html[data-theme] + localStorage ('glassTheme', gedeeld met de review-views).
PAGE = r"""<!DOCTYPE html>
<html lang="nl" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>duo-plan · Claude ✕ Codex</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%E2%9A%94%EF%B8%8F%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>try{if(localStorage.getItem('glassTheme')==='dark')document.documentElement.dataset.theme='dark'}catch(e){}</script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html[data-theme="light"] { color-scheme: light;
  --page: radial-gradient(1000px 720px at 12% -8%, #FDEBDD 0%, rgba(253,235,221,0) 56%), radial-gradient(940px 820px at 102% -4%, #DFF3EE 0%, rgba(223,243,238,0) 54%), linear-gradient(180deg,#F7F8FB 0%,#EDF0F5 100%);
  --blob1: rgba(251,146,60,.34); --blob2: rgba(45,140,240,.28); --blob3: rgba(129,140,248,.20);
  --panel: rgba(255,255,255,.62); --panel-bd: rgba(20,28,46,.10); --panel-hi: rgba(255,255,255,.9);
  --panel-shadow: 0 24px 60px -34px rgba(30,41,80,.34);
  --claude-fill: linear-gradient(180deg,rgba(251,146,60,.14),rgba(255,255,255,.5)); --claude-bd: rgba(234,120,40,.34); --claude-fg: #C2570C;
  --codex-fill: linear-gradient(180deg,rgba(45,140,240,.12),rgba(255,255,255,.5)); --codex-bd: rgba(30,110,214,.30); --codex-fg: #1E6ED6;
  --text: #1B2437; --muted: #566079; --faint: #8A93A8; --ts: #9AA2B5;
  --chip-bg: rgba(20,28,46,.055); --chip-bd: rgba(20,28,46,.12); --chip-fg: #3C465E;
  --strong: #131A2A; --link: #2563C9;
  --soft: rgba(255,255,255,.55); --soft-bd: rgba(20,28,46,.09);
  --pre-bg: rgba(20,28,46,.045); --input-bg: rgba(255,255,255,.7); --line: rgba(20,28,46,.10);
  --pill-todo-bg: rgba(20,28,46,.04); --pill-todo-fg: #7C879B; --pill-todo-bd: rgba(20,28,46,.10);
  --ok-bg: rgba(16,148,90,.12); --ok-fg: #0F8A54; --ok-bd: rgba(16,148,90,.32);
  --warn-bg: rgba(176,122,0,.12); --warn-fg: #9A6800; --warn-bd: rgba(176,122,0,.3);
  --err-bg: rgba(220,54,43,.10); --err-fg: #C4362B; --err-bd: rgba(220,54,43,.28);
  --active-bg: rgba(234,120,40,.12); --active-fg: #C2570C; --active-bd: rgba(234,120,40,.4);
  --knob-bg: #FFF7EC;
}
html[data-theme="dark"] { color-scheme: dark;
  --page: radial-gradient(1200px 700px at 15% -5%, #14213F 0%, rgba(20,33,63,0) 55%), radial-gradient(1000px 800px at 100% 0%, #241436 0%, rgba(36,20,54,0) 50%), linear-gradient(180deg,#080C18 0%,#0A0F1F 100%);
  --blob1: rgba(251,146,60,.20); --blob2: rgba(56,152,255,.18); --blob3: rgba(129,140,248,.14);
  --panel: rgba(255,255,255,.04); --panel-bd: rgba(255,255,255,.09); --panel-hi: rgba(255,255,255,.06);
  --panel-shadow: 0 30px 70px -34px rgba(0,0,0,.85);
  --claude-fill: linear-gradient(180deg,rgba(251,146,60,.08),rgba(255,255,255,.03)); --claude-bd: rgba(251,146,60,.22); --claude-fg: #FBB27A;
  --codex-fill: linear-gradient(180deg,rgba(56,152,255,.09),rgba(255,255,255,.03)); --codex-bd: rgba(96,165,250,.26); --codex-fg: #7EBBFF;
  --text: #E7EAF3; --muted: #9BA3B7; --faint: #8B93A7; --ts: #5D6580;
  --chip-bg: rgba(148,163,184,.14); --chip-bd: rgba(148,163,184,.24); --chip-fg: #C9D2E3;
  --strong: #F1F4FB; --link: #7EC8FF;
  --soft: rgba(255,255,255,.035); --soft-bd: rgba(255,255,255,.07);
  --pre-bg: rgba(0,0,0,.28); --input-bg: rgba(255,255,255,.04); --line: rgba(255,255,255,.08);
  --pill-todo-bg: rgba(255,255,255,.04); --pill-todo-fg: #7A8299; --pill-todo-bd: rgba(255,255,255,.08);
  --ok-bg: rgba(52,211,153,.14); --ok-fg: #6EE7B7; --ok-bd: rgba(52,211,153,.32);
  --warn-bg: rgba(251,191,36,.16); --warn-fg: #FCD34D; --warn-bd: rgba(251,191,36,.3);
  --err-bg: rgba(248,113,113,.16); --err-fg: #FCA5A5; --err-bd: rgba(248,113,113,.3);
  --active-bg: rgba(251,146,60,.14); --active-fg: #FBB27A; --active-bd: rgba(251,146,60,.4);
  --knob-bg: #0A0F1F;
}
@keyframes bdrift1 { 0%{transform:translate(0,0) scale(1)} 50%{transform:translate(70px,50px) scale(1.18)} 100%{transform:translate(0,0) scale(1)} }
@keyframes bdrift2 { 0%{transform:translate(0,0) scale(1.05)} 50%{transform:translate(-80px,40px) scale(.9)} 100%{transform:translate(0,0) scale(1.05)} }
@keyframes bdrift3 { 0%{transform:translate(0,0) scale(1)} 50%{transform:translate(40px,-50px) scale(1.12)} 100%{transform:translate(0,0) scale(1)} }
body { min-height: 100vh; background: var(--page); color: var(--text);
  font: 14px/1.5 'Manrope', system-ui, sans-serif; transition: background 600ms ease, color 300ms ease; overflow-x: hidden; }
.blob { position: fixed; border-radius: 50%; pointer-events: none; z-index: 0; }
.b1 { top: -160px; left: -90px; width: 460px; height: 460px; background: radial-gradient(circle,var(--blob1),transparent 62%); filter: blur(44px); animation: bdrift1 22s ease-in-out infinite; }
.b2 { top: 160px; right: -140px; width: 520px; height: 520px; background: radial-gradient(circle,var(--blob2),transparent 62%); filter: blur(50px); animation: bdrift2 27s ease-in-out infinite; }
.b3 { bottom: -180px; left: 38%; width: 480px; height: 480px; background: radial-gradient(circle,var(--blob3),transparent 64%); filter: blur(52px); animation: bdrift3 31s ease-in-out infinite; }
.wrap { position: relative; z-index: 1; max-width: 1180px; margin: 0 auto; padding: 34px 26px 90px; }

.topbar { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.kicker { font-family: 'Sora', sans-serif; font-size: 13px; letter-spacing: .22em; text-transform: uppercase; color: var(--faint); }
.theme-toggle { display: flex; align-items: center; gap: 8px; padding: 7px 8px 7px 14px; border-radius: 999px;
  border: 1px solid var(--panel-bd); background: var(--panel); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  color: var(--text); font-family: 'Manrope', sans-serif; font-size: 13px; font-weight: 600; cursor: pointer; }
.theme-word::after { content: 'Light'; }
html[data-theme="dark"] .theme-word::after { content: 'Dark'; }
.track { width: 34px; height: 20px; border-radius: 999px; background: var(--soft-bd); position: relative; display: inline-block; }
.knob { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--knob-bg);
  display: flex; align-items: center; justify-content: center; font-size: 10px;
  transition: left 260ms cubic-bezier(.4,1.3,.5,1); box-shadow: 0 1px 3px rgba(0,0,0,.35); }
.knob::after { content: '\2600'; }
html[data-theme="dark"] .knob { left: 16px; }
html[data-theme="dark"] .knob::after { content: '\263E'; }

.header { display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap; margin-bottom: 6px; }
h1 { font-family: 'Sora', sans-serif; font-weight: 700; font-size: 34px; letter-spacing: -.02em; white-space: nowrap; color: var(--strong); }
h1 .x { background: linear-gradient(90deg,#FB923C,#2DD4BF); -webkit-background-clip: text; background-clip: text; color: transparent; }
.clock { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--faint); display: flex; align-items: center; gap: 7px; font-variant-numeric: tabular-nums; }
.livedot { width: 7px; height: 7px; border-radius: 50%; background: #2DD4BF; box-shadow: 0 0 10px #2DD4BF; }
.task { font-size: 16px; color: var(--muted); margin-bottom: 22px; max-width: 900px; }

.stepper { display: flex; gap: 9px; margin: 0 0 26px; flex-wrap: wrap; }
.step { padding: 7px 16px; border-radius: 999px; font-size: 13.5px; font-weight: 600; white-space: nowrap;
  background: var(--pill-todo-bg); color: var(--pill-todo-fg); border: 1px solid var(--pill-todo-bd); }
.step.active { background: var(--active-bg); color: var(--active-fg); border-color: var(--active-bd); box-shadow: 0 0 18px -8px rgba(251,146,60,.5); }
.step.past { background: var(--ok-bg); color: var(--ok-fg); border-color: var(--ok-bd); box-shadow: 0 0 18px -8px rgba(52,211,153,.5); }
.step.past::before { content: "\2713 "; }

.agents { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
@media (max-width: 900px) { .agents { grid-template-columns: 1fr; } }
.card { border-radius: 20px; overflow: hidden; backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--panel-shadow), inset 0 1px 0 var(--panel-hi); }
.card.claude { background: var(--claude-fill); border: 1px solid var(--claude-bd); }
.card.codex { background: var(--codex-fill); border: 1px solid var(--codex-bd); }
.card-head { display: flex; align-items: center; gap: 10px; padding: 18px 22px 12px; }
.card-head .name { font-family: 'Sora', sans-serif; font-weight: 600; font-size: 19px; }
.card.claude .name { color: var(--claude-fg); } .card.codex .name { color: var(--codex-fg); }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); flex: none; }
.dot.working { background: #34D399; box-shadow: 0 0 10px #34D399; animation: pulse 1.2s ease-in-out infinite; }
.dot.done { background: #34D399; box-shadow: 0 0 10px #34D399; } .dot.error { background: var(--err-fg); box-shadow: 0 0 10px var(--err-fg); }
@keyframes pulse { 50% { opacity: .35; } }
.curstep { color: var(--faint); font-size: 12.5px; margin-left: auto; text-align: right; max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feed { height: 260px; overflow-y: auto; padding: 4px 22px 18px; font: 12px/1.65 'JetBrains Mono', ui-monospace, monospace; }
.feed .ev { display: flex; gap: 12px; }
.feed .ts { color: var(--ts); flex: none; }
.feed .step-ev { color: var(--text); font-weight: 700; font-family: 'Manrope', sans-serif; font-size: 13px; }
.feed .log-ev { color: var(--muted); }
.feed .error-ev { color: var(--err-fg); }

.regie { margin: 22px 0 40px; padding: 16px 20px; border-radius: 16px; background: var(--soft); border: 1px solid var(--soft-bd);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); color: var(--muted); font-size: 14px; }
.regie b { color: var(--strong); font-weight: 700; }

.section { margin-top: 34px; }
.section > h2 { font-family: 'Sora', sans-serif; font-weight: 600; font-size: 24px; margin-bottom: 16px; color: var(--strong); }

.conflict { border-radius: 22px; padding: 30px 32px; margin-bottom: 18px; background: var(--panel); border: 1px solid var(--panel-bd);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); box-shadow: var(--panel-shadow); }
.conflict h3 { font-family: 'Sora', sans-serif; font-weight: 600; font-size: 21px; margin-bottom: 10px; color: var(--strong); }
.conflict .summary { color: var(--muted); font-size: 15px; line-height: 1.7; margin-bottom: 24px; max-width: 82ch; }
.options { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 900px) { .options { grid-template-columns: 1fr; } }
.option { border-radius: 18px; padding: 24px 26px; display: flex; flex-direction: column; box-shadow: inset 0 1px 0 var(--panel-hi); }
.option.claude { background: var(--claude-fill); border: 1px solid var(--claude-bd); }
.option.codex { background: var(--codex-fill); border: 1px solid var(--codex-bd); }
.option .who { font-size: 12px; letter-spacing: .18em; text-transform: uppercase; font-weight: 700; margin-bottom: 12px; }
.option.claude .who { color: var(--claude-fg); } .option.codex .who { color: var(--codex-fg); }
.option .label { font-family: 'Sora', sans-serif; font-weight: 600; font-size: 18px; margin-bottom: 12px; color: var(--strong); }
.option .detail { color: var(--muted); font-size: 14px; flex: 1; }
button { cursor: pointer; border: 1px solid var(--panel-bd); background: var(--soft); color: var(--text);
  border-radius: 12px; padding: 10px 16px; font-family: 'Manrope', sans-serif; font-size: 13.5px; font-weight: 600; }
button:hover:not(:disabled) { filter: brightness(1.05); }
button:disabled { opacity: .45; cursor: default; }
.option button { margin-top: 14px; padding: 13px; font-family: 'Sora', sans-serif; font-size: 14px; font-weight: 700; border: none; }
.btn-claude { background: linear-gradient(90deg,#FB923C,#F97316); color: #1B0F04; box-shadow: 0 12px 30px -12px rgba(251,146,60,.6); }
.btn-codex { background: linear-gradient(90deg,#3B9BFF,#2563EB); color: #F2F7FF; box-shadow: 0 12px 30px -12px rgba(45,140,240,.6); }
.custom { margin-top: 22px; display: flex; gap: 12px; align-items: stretch; }
.custom textarea { flex: 1; min-height: 64px; background: var(--input-bg); border: 1px solid var(--panel-bd); border-radius: 14px;
  color: var(--text); padding: 13px 15px; font: 15px/1.5 'Manrope', sans-serif; resize: vertical; }
.custom button { padding: 0 26px; border-radius: 14px; font-family: 'Sora', sans-serif; font-size: 14px; white-space: nowrap; }
.decided { margin-top: 20px; padding: 10px 16px; border-radius: 12px; background: var(--ok-bg); border: 1px solid var(--ok-bd); color: var(--ok-fg); font-size: 14px; }

details.plan { border-radius: 14px; margin-bottom: 11px; overflow: hidden; background: var(--soft); border: 1px solid var(--soft-bd);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
details.plan > summary { cursor: pointer; padding: 16px 22px; font-weight: 600; font-size: 15.5px; list-style: none; display: flex; align-items: center; gap: 12px; color: var(--text); }
details.plan > summary::before { content: "\25B8"; color: var(--ts); font-size: 12px; transition: transform .15s; }
details.plan[open] > summary::before { transform: rotate(90deg); }
.md { padding: 4px 24px 20px; overflow-x: auto; font-size: 14.5px; line-height: 1.68; color: var(--muted); }
.md h1 { font-family: 'Sora', sans-serif; font-size: 19px; margin: 14px 0 8px; color: var(--strong); letter-spacing: 0; white-space: normal; }
.md h2 { font-family: 'Sora', sans-serif; font-size: 16.5px; margin: 14px 0 6px; color: var(--strong); }
.md h3 { font-family: 'Sora', sans-serif; font-size: 14.5px; margin: 12px 0 4px; color: var(--strong); }
.md p { margin: 6px 0; } .md ul, .md ol { margin: 6px 0 6px 22px; }
.md b { color: var(--strong); }
.md code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: var(--chip-bg); border: 1px solid var(--chip-bd); border-radius: 6px; padding: 1px 6px; color: var(--chip-fg); }
.md pre { background: var(--pre-bg); border: 1px solid var(--soft-bd); border-radius: 12px; padding: 14px 16px; overflow-x: auto; margin: 10px 0; font-family: 'JetBrains Mono', monospace; font-size: 12.5px; line-height: 1.65; }
.md pre code { background: none; border: none; padding: 0; }
.md blockquote { border-left: 3px solid var(--line); padding-left: 12px; color: var(--faint); margin: 8px 0; }
.md hr { border: none; border-top: 1px solid var(--line); margin: 14px 0; }
.md a { color: var(--link); text-decoration: none; }
.md a:hover { filter: brightness(1.15); }
.plans-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
@media (max-width: 1100px) { .plans-grid { grid-template-columns: 1fr; } }

.final { border-radius: 22px; overflow: hidden; background: var(--panel); border: 1px solid var(--ok-bd);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); box-shadow: var(--panel-shadow); }
.final .banner { padding: 16px 24px; border-bottom: 1px solid var(--line); font-family: 'Sora', sans-serif; font-weight: 600; color: var(--ok-fg); }
.final .md { padding: 10px 28px 22px; }
.approve-bar { padding: 20px 24px; border-top: 1px solid var(--line); }
.approve-bar textarea { width: 100%; background: var(--input-bg); border: 1px solid var(--panel-bd); border-radius: 14px;
  color: var(--text); padding: 13px 15px; font: 15px/1.5 'Manrope', sans-serif; min-height: 60px; resize: vertical; margin-bottom: 14px; }
.approve-actions { display: flex; gap: 12px; }
.btn-ok { border: none; border-radius: 12px; padding: 12px 22px; font-family: 'Sora', sans-serif; font-size: 14px; font-weight: 700;
  background: linear-gradient(90deg,#34D399,#10B981); color: #06281B; box-shadow: 0 12px 30px -14px rgba(52,211,153,.6); }
.btn-edit { background: var(--warn-bg); border: 1px solid var(--warn-bd); color: var(--warn-fg); border-radius: 12px; padding: 12px 22px; font-weight: 700; }
.sent { color: var(--ok-fg); font-weight: 700; padding: 8px 0; }
.empty { color: var(--faint); font-style: italic; padding: 20px; text-align: center; }
</style>
</head>
<body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
<div class="wrap">
<div class="topbar">
  <div class="kicker">duo-plan · live run</div>
  <button class="theme-toggle" onclick="toggleTheme()"><span class="theme-word"></span><span class="track"><span class="knob"></span></span></button>
</div>
<div class="header">
  <h1>Claude <span class="x">✕</span> Codex</h1>
  <div class="clock"><span class="livedot"></span><span id="elapsed"></span></div>
</div>
<div class="task" id="task"></div>
<div class="stepper" id="stepper"></div>

<div class="agents">
  <div class="card claude">
    <div class="card-head"><span class="dot" id="dot-claude"></span><span class="name">Claude</span><span class="curstep" id="cur-claude"></span></div>
    <div class="feed" id="feed-claude"><div class="empty">wachten op events…</div></div>
  </div>
  <div class="card codex">
    <div class="card-head"><span class="dot" id="dot-codex"></span><span class="name">Codex</span><span class="curstep" id="cur-codex"></span></div>
    <div class="feed" id="feed-codex"><div class="empty">wachten op events…</div></div>
  </div>
</div>
<div class="regie" id="regie" style="display:none"></div>

<div class="section" id="conflicts-section" style="display:none">
  <h2>⚖&nbsp; Jouw keuzes — de modellen zijn het oneens</h2>
  <div id="conflicts"></div>
</div>

<div class="section" id="plans-section" style="display:none">
  <h2>Plannen</h2>
  <div class="plans-grid" id="plans-grid"></div>
  <div id="reviews"></div>
</div>

<div class="section" id="final-section" style="display:none">
  <h2>🏁 Eindplan</h2>
  <div class="final">
    <div class="banner">Gezamenlijk plan — beste punten van beide modellen</div>
    <div class="md" id="final-md"></div>
    <div class="approve-bar" id="approve-bar"></div>
  </div>
</div>
</div>

<script>
function toggleTheme() {
  const h = document.documentElement;
  const t = h.dataset.theme === 'dark' ? 'light' : 'dark';
  h.dataset.theme = t;
  try { localStorage.setItem('glassTheme', t); } catch (e) {}
}

const PHASES = [
  ["planning", "Plannen"], ["cross_review", "Cross-review"], ["synthesis", "Synthese"],
  ["decision", "Jouw keuzes"], ["validation", "Validatie"], ["approval", "Akkoord"], ["done", "Klaar"]
];
const esc = s => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function md2html(src) {
  if (!src) return "";
  const blocks = [];
  src = src.replace(/```([\s\S]*?)```/g, (_, code) => {
    blocks.push("<pre><code>" + esc(code.replace(/^[^\n]*\n/, "")) + "</code></pre>");
    return "\n§B" + (blocks.length - 1) + "§\n";
  });
  const inline = t => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|\s)\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  const lines = src.split("\n");
  let html = "", list = null, para = [];
  const flushPara = () => { if (para.length) { html += "<p>" + inline(para.join(" ")) + "</p>"; para = []; } };
  const flushList = () => { if (list) { html += "</" + list + ">"; list = null; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const ul = line.match(/^\s*[-*]\s+(.*)/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (line.match(/^§B\d+§$/)) { flushPara(); flushList(); html += blocks[+line.replace(/§B?/g, "")]; }
    else if (h) { flushPara(); flushList(); html += `<h${h[1].length}>` + inline(h[2]) + `</h${h[1].length}>`; }
    else if (/^---+$/.test(line.trim())) { flushPara(); flushList(); html += "<hr>"; }
    else if (line.startsWith(">")) { flushPara(); flushList(); html += "<blockquote>" + inline(line.replace(/^>\s?/, "")) + "</blockquote>"; }
    else if (ul) { flushPara(); if (list !== "ul") { flushList(); html += "<ul>"; list = "ul"; } html += "<li>" + inline(ul[1]) + "</li>"; }
    else if (ol) { flushPara(); if (list !== "ol") { flushList(); html += "<ol>"; list = "ol"; } html += "<li>" + inline(ol[1]) + "</li>"; }
    else if (!line.trim()) { flushPara(); flushList(); }
    else para.push(line.trim());
  }
  flushPara(); flushList();
  return html;
}

let started = null, lastJSON = "";
const openPlans = new Set();

function agentView(events, agent) {
  const mine = events.filter(e => e.agent === agent);
  let status = "idle", cur = "";
  for (const e of mine) {
    if (e.type === "status") status = e.text;
    if (e.type === "step") cur = e.text;
    if (e.type === "error") status = "error";
  }
  return { mine, status, cur };
}

function renderFeed(el, events) {
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
  el.innerHTML = events.slice(-200).map(e => {
    const cls = e.type === "step" ? "step-ev" : e.type === "error" ? "error-ev" : "log-ev";
    const ts = (e.ts || "").slice(11, 19);
    return `<div class="ev"><span class="ts">${ts}</span><span class="${cls}">${esc(e.text)}</span></div>`;
  }).join("") || '<div class="empty">nog geen activiteit</div>';
  if (atBottom) el.scrollTop = el.scrollHeight;
}

function planCard(title, who, key, content) {
  const open = openPlans.has(key) ? " open" : "";
  return `<details class="plan${open}" data-key="${key}"><summary>${title}</summary><div class="md">${md2html(content)}</div></details>`;
}

async function post(path, body) {
  await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  tick();
}

function renderConflicts(control, decisions) {
  const list = control.conflicts || [];
  const section = document.getElementById("conflicts-section");
  section.style.display = list.length ? "" : "none";
  document.getElementById("conflicts").innerHTML = list.map(c => {
    const d = (decisions.decisions || {})[c.id];
    const opt = (who, o) => `
      <div class="option ${who}">
        <div class="who">${who === "claude" ? "Claude stelt voor" : "Codex stelt voor"}</div>
        <div class="label">${esc(o.label || "")}</div>
        <div class="detail md">${md2html(o.detail || "")}</div>
        <button class="btn-${who}" ${d ? "disabled" : ""} onclick='post("/decision",{id:"${c.id}",choice:"${who}"})'>Kies deze aanpak</button>
      </div>`;
    const decided = d ? `<div class="decided">✓ Gekozen: <b>${d.choice === "custom" ? "eigen instructie" : d.choice}</b>${d.note ? " — " + esc(d.note) : ""}</div>` : `
      <div class="custom">
        <textarea id="note-${c.id}" placeholder="Of geef je eigen instructie…"></textarea>
        <button onclick='post("/decision",{id:"${c.id}",choice:"custom",note:document.getElementById("note-${c.id}").value})'>Eigen keuze</button>
      </div>`;
    return `<div class="conflict"><h3>${esc(c.title)}</h3><div class="summary">${esc(c.summary || "")}</div>
      <div class="options">${opt("claude", c.options?.claude || {})}${opt("codex", c.options?.codex || {})}</div>${decided}</div>`;
  }).join("");
}

function renderApproval(control, decisions) {
  const bar = document.getElementById("approve-bar");
  const requested = control.approval_requested || 0;
  const approvals = decisions.approvals || [];
  if (!requested) { bar.innerHTML = ""; return; }
  if (approvals.length >= requested) {
    const last = approvals[approvals.length - 1];
    bar.innerHTML = `<div class="sent">${last.approved ? "✅ Akkoord verstuurd — Claude pakt het op in de chat." : "✏️ Aanpassing gevraagd — Claude verwerkt je opmerking."}</div>`;
    return;
  }
  bar.innerHTML = `
    <textarea id="approve-note" placeholder="Opmerking (optioneel bij akkoord, verplicht handig bij aanpassen)…"></textarea>
    <div class="approve-actions">
      <button class="btn-ok" onclick='post("/approval",{approved:true,note:document.getElementById("approve-note").value})'>✅ Akkoord — ga verder</button>
      <button class="btn-edit" onclick='post("/approval",{approved:false,note:document.getElementById("approve-note").value})'>✏️ Aanpassen — verwerk mijn opmerking</button>
    </div>`;
}

function render(state) {
  const { control, events, decisions, plans } = state;
  document.getElementById("task").textContent = control.title || control.task || "";
  document.title = "duo-plan · " + (control.title || "Claude ✕ Codex");
  if (!started && control.created_at) started = new Date(control.created_at);

  const idx = Math.max(0, PHASES.findIndex(p => p[0] === control.phase));
  document.getElementById("stepper").innerHTML = PHASES.map((p, i) =>
    `<span class="step ${i < idx ? "past" : i === idx ? "active" : ""}">${p[1]}</span>`).join("");

  for (const agent of ["claude", "codex"]) {
    const v = agentView(events, agent);
    document.getElementById("dot-" + agent).className = "dot " + v.status;
    document.getElementById("cur-" + agent).textContent = v.cur;
    renderFeed(document.getElementById("feed-" + agent), v.mine);
  }
  const sys = events.filter(e => e.agent === "system").slice(-3);
  const regie = document.getElementById("regie");
  regie.style.display = sys.length ? "" : "none";
  regie.innerHTML = "<b>Regie:</b> " + sys.map(e => esc(e.text)).join(" · ");

  renderConflicts(control, decisions);

  const grid = document.getElementById("plans-grid"), reviews = document.getElementById("reviews");
  const hasPlans = plans.claude_plan || plans.codex_plan;
  document.getElementById("plans-section").style.display = hasPlans ? "" : "none";
  if (hasPlans) {
    grid.innerHTML =
      (plans.claude_plan ? planCard("🟠 Plan van Claude", "claude", "claude_plan", plans.claude_plan) : "") +
      (plans.codex_plan ? planCard("🔵 Plan van Codex", "codex", "codex_plan", plans.codex_plan) : "");
    reviews.innerHTML =
      (plans.codex_review_of_claude ? planCard("🔵→🟠 Codex reviewt Claude's plan", "codex", "codex_review_of_claude", plans.codex_review_of_claude) : "") +
      (plans.claude_review_of_codex ? planCard("🟠→🔵 Claude reviewt Codex' plan", "claude", "claude_review_of_codex", plans.claude_review_of_codex) : "") +
      (plans.codex_validation ? planCard("🔵 Codex-validatie van de merge", "codex", "codex_validation", plans.codex_validation) : "");
    document.querySelectorAll("details.plan").forEach(d => {
      d.addEventListener("toggle", () => { d.open ? openPlans.add(d.dataset.key) : openPlans.delete(d.dataset.key); });
    });
  }

  const finalSection = document.getElementById("final-section");
  finalSection.style.display = plans.final_plan ? "" : "none";
  if (plans.final_plan) {
    document.getElementById("final-md").innerHTML = md2html(plans.final_plan);
    renderApproval(control, decisions);
    if (!renderApproval._scrolled && control.phase === "approval") {
      renderApproval._scrolled = true;
      finalSection.scrollIntoView({ behavior: "smooth" });
    }
  }
}

async function tick() {
  try {
    const res = await fetch("/state");
    const state = await res.json();
    const j = JSON.stringify([state.control, state.events.length, state.decisions, Object.keys(state.plans).map(k => state.plans[k].length)]);
    if (j !== lastJSON) { lastJSON = j; render(state); }
    if (started) {
      const s = Math.floor((Date.now() - started.getTime()) / 1000);
      document.getElementById("elapsed").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }
  } catch (e) { /* server weg = run voorbij; laat laatste stand staan */ }
}
tick();
setInterval(tick, 1500);
</script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f"ERROR run dir not found: {args.run_dir}", file=sys.stderr)
        return 1

    state = RunState(args.run_dir)
    port = args.port or find_free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    url = f"http://127.0.0.1:{port}"
    print(f"DASHBOARD_URL {url}", flush=True)
    if not args.no_open:
        open_browser(url)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
