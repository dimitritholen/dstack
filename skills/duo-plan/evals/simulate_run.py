#!/usr/bin/env python3
"""Replay a realistic duo-plan run against a run dir, for dashboard demos/tests.

Plays the orchestrator + both agents on a timeline: parallel planning events,
plans appearing, cross-review, synthesis, a real conflict (then WAITS for the
user's choice in the dashboard), final plan, validation, and approval (waits
again). Interactive end-to-end demo without spending a Codex run.

Usage:
  python3 simulate_run.py --run-dir DIR [--speed 1.0]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import time

SPEED = 1.0
RUN = ""


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def ev(agent: str, etype: str, text: str) -> None:
    line = json.dumps({"ts": now(), "agent": agent, "type": etype, "text": text}, ensure_ascii=False) + "\n"
    fd = os.open(os.path.join(RUN, "events.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def control(update: dict) -> None:
    path = os.path.join(RUN, "control.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.update(update)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def plan(name: str, content: str) -> None:
    with open(os.path.join(RUN, "plans", name), "w", encoding="utf-8") as f:
        f.write(content)


def nap(seconds: float) -> None:
    time.sleep(seconds / SPEED)


def wait_decisions(ids: list) -> dict:
    path = os.path.join(RUN, "decisions.json")
    while True:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        decisions = data.get("decisions", {})
        if all(i in decisions for i in ids):
            return {i: decisions[i] for i in ids}
        time.sleep(0.5)


def wait_approval(min_count: int) -> dict:
    path = os.path.join(RUN, "decisions.json")
    while True:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        approvals = data.get("approvals", [])
        if len(approvals) >= min_count:
            return approvals[-1]
        time.sleep(0.5)


CLAUDE_PLAN = """# Ontwikkelplan

## Aanpak (3-5 zinnen)
Voeg rate limiting toe als ASP.NET Core middleware met een sliding window per API-key,
opgeslagen in de bestaande Redis-instantie. Configuratie per endpoint-groep via appsettings,
zodat productbeheer limieten kan bijstellen zonder deploy.

## Stappen
1. `src/Api/Middleware/RateLimitMiddleware.cs` — nieuwe middleware, sliding window via Redis `INCR`+`EXPIRE`.
2. `src/Api/Configuration/RateLimitOptions.cs` — options-pattern met per-groep limieten.
3. `src/Api/Program.cs` — registratie vóór authenticatie-middleware.
4. `appsettings.json` — defaults: 100 req/min per key.
5. 429-responses met `Retry-After` header.

## Risico's & mitigaties
- Redis-uitval → fail-open met circuit breaker; loggen, niet blokkeren.
- Clock skew bij sliding window → Redis server time gebruiken.

## Expliciete keuzes
- **Sliding window** i.p.v. fixed window (afgewezen: burst op window-grens).
- **Redis** i.p.v. in-memory (afgewezen: werkt niet bij meerdere instances).

## Testaanpak
Unit tests op window-logica; integratietest die 429 + `Retry-After` verifieert.
"""

CODEX_PLAN = """# Ontwikkelplan

## Aanpak
Gebruik het ingebouwde `Microsoft.AspNetCore.RateLimiting` (.NET 8) met een custom
`IRateLimiterPolicy` per API-key en een token bucket. Geen extra infra: de policy
draait in-process met een `IDistributedCache`-backing voor multi-instance.

## Stappen
1. `src/Api/Program.cs` — `AddRateLimiter` met named policy "api-key".
2. `src/Api/RateLimiting/ApiKeyRateLimiterPolicy.cs` — token bucket, partitie per key.
3. `src/Api/RateLimiting/DistributedTokenStore.cs` — IDistributedCache-backing.
4. OpenAPI-documentatie van 429-gedrag bijwerken.

## Risico's & mitigaties
- Token bucket in-process is per instance; distributed store maakt het consistent.

## Expliciete keuzes
- **Framework-native RateLimiting** i.p.v. eigen middleware (afgewezen: zelf onderhouden
  concurrency-code terwijl het framework dit al goed doet).
- **Token bucket** i.p.v. sliding window (afgewezen: sliding window is duurder per request).

## Testaanpak
Integratietests met `WebApplicationFactory`; load-test met 2 instances tegen gedeelde cache.
"""

CODEX_REVIEW = """# Review van Claude's plan

## Sterker dan mijn plan
- Expliciete fail-open strategie bij Redis-uitval — neem ik over.
- `Retry-After` header expliciet benoemd.

## Zwakker of riskanter
- Eigen middleware betekent zelf concurrency-correctheid bewijzen; .NET 8 heeft dit ingebouwd.

## CONFLICT: implementatiebasis
Claude bouwt een eigen Redis-middleware; ik gebruik framework-native
`Microsoft.AspNetCore.RateLimiting`. Beide werken, maar het is een onverenigbare
architectuurkeuze: eigen code + volledige controle vs. framework-onderhoud + minder code.

## Eindoordeel
Combineer: framework-native basis, Claude's fail-open + Retry-After, mijn distributed store.
"""

CLAUDE_REVIEW = """# Review van Codex' plan

## Sterker dan mijn plan
- Framework-native `AddRateLimiter` scheelt eigen concurrency-code — serieus voordeel.
- Load-test met 2 instances is een gat in mijn testaanpak.

## Zwakker of riskanter
- Geen fail-open gedrag gedefinieerd bij cache-uitval.
- Token bucket-keuze niet onderbouwd tegen de burst-eisen uit de opdracht.

## CONFLICT: implementatiebasis
Zie boven — eigen Redis-middleware (mijn plan) vs. framework-native (Codex). De keuze
bepaalt de hele bestandsstructuur, dus dit moet vooraf beslist worden.

## Eindoordeel
Codex' basis + mijn operationele hardening lijkt de beste combinatie.
"""

FINAL_TEMPLATE = """# Eindplan — Rate limiting per API-key

## Aanpak
{basis}

Fail-open bij store-uitval (circuit breaker + logging), 429-responses met
`Retry-After`, configuratie via options-pattern zodat limieten zonder deploy
bijgesteld kunnen worden.

## Stappen
{stappen}

## Testaanpak
Unit tests op de limietlogica, integratietests via `WebApplicationFactory`
(429 + `Retry-After`), en een load-test met 2 instances tegen de gedeelde store.

## Herkomst
- Basisarchitectuur: **{herkomst_basis}**
- Fail-open + Retry-After: Claude
- Distributed store + multi-instance load-test: Codex
- Options-pattern configuratie: beide plannen onafhankelijk
"""

STEPS_NATIVE = """1. `src/Api/Program.cs` — `AddRateLimiter` met named policy "api-key".
2. `src/Api/RateLimiting/ApiKeyRateLimiterPolicy.cs` — partitie per API-key.
3. `src/Api/RateLimiting/DistributedTokenStore.cs` — `IDistributedCache`-backing (Redis).
4. `src/Api/Configuration/RateLimitOptions.cs` — per-groep limieten uit appsettings.
5. Circuit breaker rond de store: bij uitval fail-open + warning-log.
6. OpenAPI-documentatie van het 429-gedrag."""

STEPS_CUSTOM = """1. `src/Api/Middleware/RateLimitMiddleware.cs` — sliding window via Redis `INCR`+`EXPIRE`.
2. `src/Api/Configuration/RateLimitOptions.cs` — per-groep limieten uit appsettings.
3. `src/Api/Program.cs` — registratie vóór authenticatie.
4. Circuit breaker rond Redis: bij uitval fail-open + warning-log.
5. OpenAPI-documentatie van het 429-gedrag."""


def main() -> None:
    global SPEED, RUN
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()
    SPEED, RUN = args.speed, args.run_dir

    for sub in ("input", "logs", "plans"):
        os.makedirs(os.path.join(RUN, sub), exist_ok=True)
    with open(os.path.join(RUN, "control.json"), "w", encoding="utf-8") as f:
        json.dump({
            "title": "DEMO · Rate limiting per API-key",
            "task": "Voeg per-API-key rate limiting toe aan de publieke API, configureerbaar zonder deploy.",
            "phase": "planning",
            "created_at": now(),
            "approval_requested": 0,
            "conflicts": [],
            "files": {
                "claude_plan": "plans/claude-plan.md",
                "codex_plan": "plans/codex-plan.md",
                "codex_review_of_claude": "plans/codex-review-of-claude.md",
                "claude_review_of_codex": "plans/claude-review-of-codex.md",
                "codex_validation": "plans/codex-validation.md",
                "final_plan": "plans/final-plan.md",
            },
        }, f, ensure_ascii=False, indent=2)

    ev("system", "step", "Run gestart — beide planners vertrekken parallel")
    ev("claude", "status", "working"); ev("codex", "status", "working")
    ev("claude", "step", "Leest de opdracht en verkent src/Api"); nap(2)
    ev("codex", "step", "Codex gestart: stelt plan op"); nap(2)
    ev("codex", "log", "▶ bash -lc 'ls src/Api' in ~/repo")
    ev("claude", "step", "Analyseert bestaande middleware-pipeline"); nap(3)
    ev("codex", "step", "Examining existing middleware and DI setup"); nap(2)
    ev("claude", "log", "Redis-client al aanwezig in DI — herbruikbaar"); nap(2)
    ev("codex", "log", "▶ bash -lc 'rg RateLimit -l' in ~/repo"); nap(2)
    ev("codex", "step", "Weighing built-in RateLimiting middleware vs custom"); nap(2)
    ev("claude", "step", "Schrijft het plan"); nap(3)
    plan("claude-plan.md", CLAUDE_PLAN)
    ev("claude", "status", "done"); ev("claude", "step", "Plan klaar")
    ev("system", "step", "Claude is klaar — wachten op Codex"); nap(4)
    ev("codex", "log", "tokens: 12,480")
    ev("codex", "step", "Schrijft eindresultaat (stelt plan op)"); nap(2)
    plan("codex-plan.md", CODEX_PLAN)
    ev("codex", "status", "done"); ev("codex", "step", "Klaar: stelt plan op")

    control({"phase": "cross_review"})
    ev("system", "step", "Beide plannen binnen — cross-review gestart")
    ev("claude", "status", "working"); ev("codex", "status", "working")
    ev("claude", "step", "Leest het plan van Codex"); nap(2)
    ev("codex", "step", "Codex gestart: reviewt Claude's plan"); nap(3)
    ev("claude", "log", "AddRateLimiter bestaat inderdaad sinds .NET 7 — checkt versie"); nap(2)
    ev("codex", "log", "▶ bash -lc 'rg StackExchange.Redis -l'"); nap(3)
    plan("codex-review-of-claude.md", CODEX_REVIEW)
    ev("codex", "status", "done"); ev("codex", "step", "Review klaar — 1 conflict gemarkeerd"); nap(2)
    plan("claude-review-of-codex.md", CLAUDE_REVIEW)
    ev("claude", "status", "done"); ev("claude", "step", "Review klaar — 1 conflict gemarkeerd")

    control({"phase": "synthesis"})
    ev("system", "step", "Synthese: sterkste punten worden samengevoegd"); nap(3)
    ev("system", "step", "Overgenomen van Claude: fail-open + Retry-After"); nap(2)
    ev("system", "step", "Overgenomen van Codex: distributed store + load-test"); nap(2)
    plan("final-plan.md", FINAL_TEMPLATE.format(
        basis="> ⚖️ Openstaande keuze: zie beslissing c1 in het dashboard",
        stappen="_(afhankelijk van beslissing c1)_", herkomst_basis="jouw keuze (c1)"))

    control({"phase": "decision", "conflicts": [{
        "id": "c1",
        "title": "Implementatiebasis: eigen middleware of framework-native?",
        "summary": "Beide reviews markeren dit als onverenigbaar — de keuze bepaalt de volledige bestandsstructuur.",
        "options": {
            "claude": {"label": "Eigen Redis-middleware (sliding window)",
                        "detail": "Volledige controle over het algoritme; sliding window voorkomt burst op window-grenzen. **Nadeel**: zelf concurrency-correctheid onderhouden."},
            "codex": {"label": "Framework-native RateLimiting (.NET 8, token bucket)",
                       "detail": "`Microsoft.AspNetCore.RateLimiting` met custom policy per API-key. Minder eigen code, door het framework onderhouden. **Nadeel**: minder controle over het algoritme."},
        },
    }]})
    ev("system", "step", "⚖️ 1 echte tegenstrijdigheid — jouw keuze is nodig in het dashboard")
    decision = wait_decisions(["c1"])["c1"]
    choice = decision["choice"]
    ev("system", "step", f"Beslissing c1 ontvangen: {choice}" + (f" — {decision['note']}" if decision.get("note") else ""))

    if choice == "claude":
        basis, stappen, herkomst = "Eigen Redis-middleware met sliding window per API-key.", STEPS_CUSTOM, "Claude (gebruikerskeuze)"
    elif choice == "codex":
        basis, stappen, herkomst = "Framework-native `Microsoft.AspNetCore.RateLimiting` met een custom policy per API-key en token bucket.", STEPS_NATIVE, "Codex (gebruikerskeuze)"
    else:
        basis, stappen, herkomst = f"Eigen instructie van de gebruiker: {decision.get('note', '')}", STEPS_NATIVE, "gebruiker (eigen instructie)"
    plan("final-plan.md", FINAL_TEMPLATE.format(basis=basis, stappen=stappen, herkomst_basis=herkomst))

    control({"phase": "validation"})
    ev("system", "step", "Codex valideert de merge"); ev("codex", "status", "working")
    ev("codex", "step", "Codex gestart: valideert de merge"); nap(4)
    plan("codex-validation.md", "VERDICT: OK\n\nDe merge bevat de kern van beide plannen; de gebruikerskeuze is consequent doorgevoerd.")
    ev("codex", "status", "done"); ev("codex", "step", "Validatie: VERDICT OK")

    control({"phase": "approval", "approval_requested": 1})
    ev("system", "step", "🏁 Eindplan staat klaar — akkoord gevraagd in het dashboard")
    verdict = wait_approval(1)
    if verdict["approved"]:
        control({"phase": "done"})
        ev("system", "step", "✅ Akkoord ontvangen — demo compleet")
    else:
        ev("system", "step", f"✏️ Aanpassing gevraagd: {verdict.get('note', '')} (demo stopt hier)")
    print("SIMULATION_DONE")


if __name__ == "__main__":
    main()
