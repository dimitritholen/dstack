---
name: duo-plan
description: "Claude and OpenAI's Codex CLI each independently plan the same development task in parallel, cross-review each other's plan, and merge the best of both into one final plan; real contradictions go to the user to decide. Use for non-trivial development tasks where the user wants two independent AI perspectives before code is written. Triggers: '/duo-plan', 'duo plan', 'plan battle', 'laat claude en codex allebei een plan maken', 'parallel plannen', 'twee plannen naast elkaar'. Not for reviewing code diffs or PRs: that's review-vs-spec."
---

# duo-plan

Claude en Codex maken **tegelijk, onafhankelijk** een ontwikkelplan voor dezelfde
opdracht. Een live HTML-dashboard toont wie waarmee bezig is. Daarna reviewen ze
elkaars plan, jij (de orchestrator) merget de beste punten, echte tegenstrijdigheden
legt het dashboard als A/B-diff aan de gebruiker voor, Codex valideert de merge, en
de gebruiker geeft akkoord met één knop.

Jij bent hier de **regisseur**: je plant zelf niet mee in de eerste fase (dat doet
een Claude-subagent, zodat het écht onafhankelijk en parallel gebeurt), maar je
bewaakt de fases, schrijft `control.json`, en doet de synthese.

## Wanneer wel, wanneer niet

**Wel**: niet-triviale ontwikkeltaken waar twee onafhankelijke perspectieven lonen —
architectuurkeuzes, refactors, migraties, features met meerdere valide aanpakken.

**Niet**:
- Snelle second opinion op een bestaand plan → vraag Codex rechtstreeks, geen volledige duo-plan-run
- Review van code/diff/PR → `/review-vs-spec`
- Triviale taken — twee modellen laten plannen voor een one-liner is verspilling; zeg dat eerlijk.

## Vereisten

- `codex` CLI op `$PATH`, ingelogd (`codex login`). Bij een auth-fout in de logs:
  stop en meld het — niet stiekem workarounden.
- Referenties: `references/state-schema.md` (run-dir layout, control.json,
  single-writer regels — **eerst lezen**) en `references/prompts.md` (alle
  prompt-koppen per fase).

## Fase 0 — Setup

1. Kies de run dir: `$CLAUDE_JOB_DIR/tmp/duo-plan-<slug>` als die env var bestaat,
   anders `/tmp/duo-plan-<slug>-$$` (slug = 2-4 woorden uit de taak). Maak de
   subdirs `input/`, `logs/`, `plans/` aan.
2. Schrijf `control.json` volgens `references/state-schema.md`: title, task,
   `phase: "planning"`, `created_at` (nu), `approval_requested: 0`, lege
   `conflicts`, en de volledige `files`-map (vooraf registreren is veilig — het
   dashboard toont panelen pas als het bestand bestaat).
3. Start het dashboard (achtergrond, blijft de hele run draaien):
   ```bash
   python3 ~/.claude/skills/duo-plan/scripts/serve_dashboard.py --run-dir "$RUN_DIR" \
     > "$RUN_DIR/logs/server.log" 2>&1
   ```
   via `Bash` met `run_in_background: true`. Lees de `DASHBOARD_URL`-regel uit
   het log en geef die **meteen** aan de gebruiker — de browser opent vanzelf,
   maar de link hoort ook in de chat.
4. Log de aftrap:
   ```bash
   python3 ~/.claude/skills/duo-plan/scripts/log_event.py --run-dir "$RUN_DIR" \
     --agent system --type step --text "Run gestart — beide planners vertrekken parallel"
   ```

## Fase 1 — Parallel plannen

Stel eerst `input/codex-plan-input.md` samen: prompt-kop 1 uit
`references/prompts.md`, dan opdracht + repo-context + relevante bestanden
(zelfde recept als codex-review: Codex ziet alléén dit bestand).

Start dan **in één beurt** drie achtergrondtaken:

1. **Codex** (Bash, `run_in_background: true`):
   ```bash
   codex exec --sandbox read-only --color never \
     -c model_reasoning_effort=high -c model_reasoning_summary=concise \
     --output-last-message "$RUN_DIR/plans/codex-plan.md" \
     - < "$RUN_DIR/input/codex-plan-input.md" > "$RUN_DIR/logs/codex-plan.log" 2>&1
   ```
2. **Watcher** (Bash, `run_in_background: true`) — vertaalt de Codex-log live naar dashboard-events:
   ```bash
   python3 ~/.claude/skills/duo-plan/scripts/codex_watcher.py --run-dir "$RUN_DIR" \
     --log-file "$RUN_DIR/logs/codex-plan.log" \
     --done-file "$RUN_DIR/plans/codex-plan.md" --label "stelt plan op"
   ```
3. **Claude-planner**: `Agent` tool (subagent, achtergrond) met prompt-template 2
   uit `references/prompts.md` — inclusief de verplichte `log_event.py`-calls; dat
   is wat de Claude-kolom van het dashboard levend maakt.

Meld de gebruiker in één bericht: beide planners draaien, de dashboard-URL, en dat
dit afhankelijk van de taak 5-20 minuten kan duren.

**Wachten: uitsluitend op completion-notificaties.** Nooit `sleep`+`tail` in één
call, nooit poll-loops in de chat. Zodra één van de twee klaar is, log dat als
system-event; zodra beide klaar zijn → fase 2. Faalt één kant (auth-fout, crash):
log een error-event, meld het eerlijk, en vraag of de gebruiker wil doorgaan met
alleen het overgebleven plan (dan degradeert de run tot een enkelvoudig plan met
review — nog steeds nuttig).

## Fase 2 — Cross-review

Zet `phase: "cross_review"` in control.json en log een system-event. Start weer
parallel in één beurt:

1. **Codex reviewt Claude's plan**: stel `input/codex-review-input.md` samen
   (prompt-kop 3: eerlijk benoemen wat beter is, wat zwakker, en `CONFLICT:`-koppen
   voor onverenigbare keuzes) en draai `codex exec` + watcher zoals in fase 1, met
   `--output-last-message "$RUN_DIR/plans/codex-review-of-claude.md"`,
   log `logs/codex-review.log`, label "reviewt Claude's plan".
2. **Claude reviewt Codex' plan**: nieuwe subagent met prompt-template 4.

Beide reviews verschijnen automatisch in het dashboard zodra de bestanden bestaan.

## Fase 3 — Synthese (dit doe jij zelf)

Zet `phase: "synthesis"`, log system-events terwijl je werkt ("Vergelijkt de
stappenplannen", "Neemt Codex' rollback-aanpak over", …) — de gebruiker kijkt mee.

Lees alle vier de documenten. Bouw het gecombineerde plan: neem van elk plan de
aantoonbaar sterkste onderdelen (de cross-reviews wijzen ze aan), en schrijf een
concept naar `plans/final-plan.md` met onderaan een sectie **"Herkomst"**: per
hoofdonderdeel of het van Claude, Codex of beide kwam — dat maakt de samenwerking
toetsbaar.

**Naamgeving-vangnet**: de prompts eisen derde persoon ("Claude: …" / "Codex: …"),
maar modellen verspreken zich soms alsnog in "ik"/"mijn plan" — en in het
dashboard is onduidelijk wie "ik" dan is. Neem je tekst over uit een plan of
review (in het eindplan, in conflict-opties, in samenvattingen), vervang dan
elke eerste- of tweede-persoonsverwijzing door de modelnaam.

**Conflicten**: verzamel de `CONFLICT:`-koppen uit beide reviews plus wat je zelf
aan onverenigbaarheden ziet. Wees streng: alléén echte tegenstrijdigheden
(botsende architectuur, onverenigbare volgorde/scope) worden een conflict —
aanvullende verschillen merge je gewoon. In het concept-eindplan markeer je de
plek met `> ⚖️ Openstaande keuze: zie beslissing <id> in het dashboard`.

- **Geen conflicten** → direct naar fase 5.
- **Wel conflicten** → schrijf ze in `control.json` (schema in state-schema.md,
  neutrale beschrijving van beide opties), zet `phase: "decision"`, en start:
  ```bash
  python3 ~/.claude/skills/duo-plan/scripts/wait_decision.py --run-dir "$RUN_DIR" \
    --for conflicts --ids c1,c2
  ```
  (Bash, `run_in_background: true`). Meld de gebruiker dat het dashboard om
  keuzes vraagt. De completion-notificatie brengt de beslissingen
  (`DECISIONS {...}`); bij `choice: "custom"` is de `note` de instructie.

## Fase 4 — Beslissingen verwerken

Verwerk elke keuze in `plans/final-plan.md` (vervang de ⚖️-markeringen), vermeld
in "Herkomst" dat het een gebruikerskeuze was, en log per beslissing een
system-event.

## Fase 5 — Codex-validatie van de merge

Zet `phase: "validation"`. Stel `input/codex-validate-input.md` samen (prompt-kop
5: eindplan + beslissingen + beide oorspronkelijke plannen) en draai `codex exec`
+ watcher met `-c model_reasoning_effort=medium`, output
`plans/codex-validation.md`, label "valideert de merge".

- `VERDICT: OK` → fase 6.
- `VERDICT: ISSUES` → kleine punten verwerk je direct in final-plan.md (log wat je
  aanpast); een nieuw echt conflict wordt een nieuwe beslisronde (nieuwe id, terug
  naar fase 3-flow). Maximaal één extra validatiepass — daarna leg je resterende
  twijfels gewoon in het eindplan vast en ga je door; eindeloos pingpongen tussen
  modellen levert geen beter plan op.

## Fase 6 — Akkoord van de gebruiker

Verhoog `approval_requested` met 1, zet `phase: "approval"`, en start:
```bash
python3 ~/.claude/skills/duo-plan/scripts/wait_decision.py --run-dir "$RUN_DIR" \
  --for approval --min-count <approval_requested>
```
(achtergrond). Meld de gebruiker dat het eindplan met akkoord-knop in het
dashboard staat.

- **Akkoord** → zet `phase: "done"`, log een afsluitend system-event, en toon in
  de chat: het volledige eindplan (of bij >200 regels: kernpunten + pad naar
  `plans/final-plan.md`), plus de vraag wat er moet gebeuren — zelfde drieluik
  als codex-review: (1) plan is klaar, stop hier; (2) direct implementeren (in
  een worktree; vraag of subagents gewenst zijn); (3) nog aanpassen in chat.
  **Implementeer niets zonder expliciete go.**
- **Aanpassen** (met note) → verwerk de opmerking in final-plan.md, log wat je
  wijzigde, en herhaal fase 6 (`approval_requested` weer +1). Raakt de opmerking
  een fundamentele keuze, doe dan eerst een verkorte validatiepass (fase 5).

Bewaar de complete run dir — input, logs, plannen, beslissingen. De gebruiker kan
er later op terugkomen ("waarom koos Codex ook alweer voor X?").

## Waarom deze opzet

- **Subagent als Claude-planner, jij als regisseur**: als jij zelf zou plannen, kan
  er niets parallel lopen en besmet jouw plan je latere synthese-oordeel.
  Onafhankelijkheid is het hele punt van twee modellen.
- **events.jsonl append-only + O_APPEND**: drie processen loggen tegelijk zonder
  locking; control.json (alleen jij) en decisions.json (alleen de server) hebben
  elk precies één schrijver. Geen races, geen corrupte JSON.
- **De watcher** maakt Codex' zwarte doos transparant: reasoning-samenvattingen en
  repo-commando's worden live dashboard-events, net zoals de log_event-calls dat
  voor de Claude-subagent doen.
- **Alleen échte tegenstrijdigheden naar de gebruiker**: elke voorgelegde keuze
  kost aandacht; aanvullende punten mergen is jouw werk, niet dat van de gebruiker.
- **Herkomst-sectie in het eindplan**: maakt zichtbaar wat de tweede planner
  daadwerkelijk opleverde — anders is nooit te beoordelen of duo-plan zijn kosten
  waard is.
- **wait_decision.py als achtergrondproces**: de harness wekt je bij een klik in
  de browser; jij pollt nooit.

## Anti-patterns

- ❌ Zelf (als orchestrator) het Claude-plan schrijven i.p.v. een subagent — dan is er geen parallellisme en geen onafhankelijke synthese.
- ❌ `sleep` + `tail` in één Bash-call of poll-loops — wacht op completion-notificaties.
- ❌ Elk verschilletje als conflict voorleggen — alleen onverenigbare keuzes; de rest merge jij.
- ❌ In decisions.json schrijven — die is exclusief van de server; nieuwe rondes = nieuwe ids / hogere `approval_requested`.
- ❌ Codex' plan of review samenvatten in eigen woorden in het dashboard — de bestanden zelf zijn de bron; het dashboard rendert ze integraal.
- ❌ Na akkoord direct gaan implementeren zonder expliciete go in de chat.
- ❌ De run dir opruimen na afloop.
