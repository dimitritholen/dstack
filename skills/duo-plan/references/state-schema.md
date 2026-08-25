# duo-plan run-dir schema

Eén run = één directory. Alles wat het dashboard toont en alles wat de gebruiker
beslist, leeft hier. Bewaar de run dir na afloop — niet opruimen.

```
<run-dir>/
├── control.json      # regie-state — ALLEEN de orchestrator schrijft dit
├── events.jsonl      # append-only event feed — iedereen mag appenden (O_APPEND)
├── decisions.json    # gebruikerskeuzes — ALLEEN serve_dashboard.py schrijft dit
├── input/            # self-contained inputbestanden voor codex exec
│   ├── codex-plan-input.md
│   ├── codex-review-input.md
│   └── codex-validate-input.md
├── logs/             # ruwe codex-stdout per fase + serverlog
│   ├── codex-plan.log
│   ├── codex-review.log
│   ├── codex-validate.log
│   └── server.log
└── plans/            # de inhoudelijke documenten
    ├── claude-plan.md
    ├── codex-plan.md
    ├── codex-review-of-claude.md
    ├── claude-review-of-codex.md
    ├── codex-validation.md
    └── final-plan.md
```

## Single-writer discipline (waarom er geen races zijn)

| Bestand         | Schrijver                            | Mechanisme                     |
|-----------------|--------------------------------------|--------------------------------|
| `events.jsonl`  | iedereen (subagent, watcher, orch.)  | één JSON-regel per event, O_APPEND |
| `control.json`  | alleen de orchestrator (jij)         | Write/Edit; server is tolerant voor half-geschreven JSON |
| `decisions.json`| alleen de dashboard-server           | atomic write (tmp + rename)    |

De orchestrator leest decisions.json wel (via wait_decision.py) maar schrijft er
nooit in. Nieuwe beslisrondes krijgen nieuwe conflict-ids en een opgehoogd
`approval_requested` — er wordt nooit iets gewist.

## control.json

```json
{
  "title": "Korte titel voor in de header",
  "task": "De opdracht in 1-3 zinnen",
  "phase": "planning",
  "created_at": "2026-07-11T14:03:22",
  "approval_requested": 0,
  "conflicts": [],
  "files": {
    "claude_plan": "plans/claude-plan.md",
    "codex_plan": "plans/codex-plan.md",
    "codex_review_of_claude": "plans/codex-review-of-claude.md",
    "claude_review_of_codex": "plans/claude-review-of-codex.md",
    "codex_validation": "plans/codex-validation.md",
    "final_plan": "plans/final-plan.md"
  }
}
```

- **phase**: `planning` → `cross_review` → `synthesis` → `decision` → `validation` → `approval` → `done`.
  Sla `decision` over als er geen conflicten zijn. Bij een afgekeurd eindplan ga je
  terug naar `synthesis` en daarna opnieuw vooruit.
- **files**: paden relatief aan de run dir. Zet ze er allemaal vanaf het begin in —
  het dashboard toont een paneel pas zodra het bestand bestaat, dus vooraf
  registreren is veilig.
- **approval_requested**: integer, start op 0. Verhoog met 1 telkens wanneer je een
  (nieuw) eindplan ter goedkeuring voorlegt. Het dashboard toont de akkoord-knoppen
  zolang `len(approvals) < approval_requested`.
- **conflicts**: alleen ECHTE tegenstrijdigheden (zie SKILL.md). Ids nooit hergebruiken.

```json
{
  "id": "c1",
  "title": "Migratiestrategie",
  "summary": "Claude wil een expand/contract-migratie, Codex een big-bang met maintenance window.",
  "options": {
    "claude": { "label": "Expand/contract", "detail": "Markdown met de kern van Claude's aanpak + waarom." },
    "codex":  { "label": "Big-bang",        "detail": "Markdown met de kern van Codex' aanpak + waarom." }
  }
}
```

## events.jsonl

Eén JSON-object per regel:

```json
{"ts": "2026-07-11T14:04:01", "agent": "claude", "type": "step", "text": "Analyseert de auth-module"}
```

- **agent**: `claude` | `codex` | `system` (regie-events van de orchestrator).
- **type**: `step` (mijlpaal, wordt "huidige activiteit"), `log` (informatief),
  `status` (`working`/`done`/`error` — stuurt het statuslampje), `error`.

## decisions.json (alleen lezen!)

```json
{
  "decisions": {
    "c1": { "choice": "claude", "note": "", "ts": "…" },
    "c2": { "choice": "custom", "note": "Doe optie A maar met feature flag", "ts": "…" }
  },
  "approvals": [
    { "approved": false, "note": "Stap 3 mist rollback", "ts": "…" },
    { "approved": true,  "note": "", "ts": "…" }
  ]
}
```

`choice` is `claude`, `codex` of `custom`; bij `custom` staat de instructie in `note`.
`approvals` is een append-only lijst: element N hoort bij goedkeuringsronde N+1.
