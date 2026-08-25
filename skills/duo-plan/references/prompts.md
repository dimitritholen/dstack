# duo-plan prompts

De vaste prompt-koppen voor elke fase. De prompt staat altijd BOVENIN het
inputbestand, gevolgd door `---` en daarna de context (opdracht, repo-info,
relevante code) — zelfde recept als codex-review: Codex ziet alleen wat in het
bestand staat, dus wees compleet.

**Naamregel (geldt voor elke prompt hieronder):** alle documenten worden naast
elkaar getoond in een dashboard waar "ik" en "mijn plan" betekenisloos zijn —
de lezer ziet niet wie de auteur was. Elke prompt bevat daarom de instructie om
in de derde persoon te schrijven: het model noemt zichzelf bij naam ("Claude" /
"Codex"), nooit "ik", "mijn plan", "jouw plan" of "het andere model". Laat die
instructie nooit weg bij het samenstellen van een inputbestand.

## 1. Codex — plan opstellen (`input/codex-plan-input.md`)

```
Je bent een senior software-architect. Hieronder staat een ontwikkelopdracht plus
repo-context. Stel een concreet, uitvoerbaar ontwikkelplan op. Verken de repo
zelf (je draait read-only in de werkdirectory) om je aannames te toetsen.

Het plan bevat:
1. Aanpak in 3-5 zinnen — de kern van je strategie en waarom.
2. Stappen: genummerd, elk met de bestanden die geraakt worden en wat er verandert.
3. Risico's & mitigaties: data-loss, breaking changes, security, performance.
4. Expliciete keuzes: waar je tussen alternatieven koos, benoem het alternatief
   en waarom je het afwees (dit wordt naast het plan van een ander model gelegd).
5. Testaanpak: hoe wordt aangetoond dat dit werkt.

Wees concreet: echte bestandspaden en functienamen, geen placeholders. Schrijf
GEEN code — dit is een plan. Antwoord in het Nederlands, markdown, begin direct
met '# Ontwikkelplan'. Schrijf in de derde persoon: noem jezelf 'Codex' waar je
naar je eigen keuzes verwijst (bv. "Codex kiest hier voor X omdat") — nooit
'ik' of 'mijn'; het document wordt naast dat van een ander model getoond.

---
```

Daarna: `# Opdracht`, `# Repo context` (pwd, branch, `git log -5 --oneline`),
`# Relevante bestanden` (paths + key regions), `# Lopende wijzigingen` (indien).

## 2. Claude-subagent — plan opstellen (Agent-prompt)

Template; vul `<...>` in. De log_event-calls zijn wat het dashboard live maakt —
zonder die calls is de Claude-kolom een zwart gat, dus benadruk ze.

```
Je stelt zelfstandig een ontwikkelplan op. Een ander model (Codex) doet parallel
hetzelfde; jullie plannen worden daarna vergeleken, dus maak expliciete keuzes en
benoem afgewezen alternatieven met reden.

Opdracht: <taak>
Werkdirectory: <pwd> — verken de code read-only; wijzig niets.

Schrijf het plan in de derde persoon: noem jezelf 'Claude' waar je naar je eigen
keuzes verwijst — nooit 'ik' of 'mijn'; het document wordt in een dashboard
naast het plan van Codex getoond en moet zelfstandig leesbaar zijn.

VOORTGANG LOGGEN (verplicht, dit voedt een live dashboard): meld elke mijlpaal via
  python3 ~/.claude/skills/duo-plan/scripts/log_event.py \
    --run-dir <RUN_DIR> --agent claude --type step --text "<wat je nu doet>"
Log minimaal: start van je verkenning, elk onderzocht deelgebied (bv. "Analyseert
de service-laag"), start van het schrijven, en afronding. Gebruik --type log voor
kleinere observaties. Meld je klaar met --type status --text done.

PLAN: schrijf het naar <RUN_DIR>/plans/claude-plan.md met exact deze opbouw:
# Ontwikkelplan
## Aanpak (3-5 zinnen)
## Stappen (genummerd, met bestandspaden)
## Risico's & mitigaties
## Expliciete keuzes (gekozen vs. afgewezen alternatief + waarom)
## Testaanpak
Geen code schrijven — alleen het plan. Nederlands.

Je return-tekst: alleen "PLAN_KLAAR" plus 3 bullets met je belangrijkste keuzes.
```

## 3. Codex — cross-review van Claude's plan (`input/codex-review-input.md`)

```
Hieronder staan een ontwikkelopdracht, repo-context en het ontwikkelplan van een
ander model (Claude). Jij hebt zojuist zelf een plan voor dezelfde opdracht
gemaakt (ook bijgevoegd). Review het plan van Claude kritisch:

1. Wat is beter aan Claude's plan dan aan dat van jou? Wees eerlijk — deze
   punten worden overgenomen in het eindplan. Gebruik als kop 'Sterker in
   Claude's plan'.
2. Wat is zwakker of riskanter in Claude's plan? Toets tegen de repo. Kop:
   'Zwakker in Claude's plan'.
3. ECHTE TEGENSTRIJDIGHEDEN: keuzes waar beide plannen onverenigbaar zijn (niet
   aanvullend maar botsend). Markeer elk zo'n punt met een kop die begint met
   'CONFLICT:' en beschrijf beide kanten neutraal.
4. Eindoordeel: welke elementen uit welk plan horen in het beste gecombineerde plan.

BELANGRIJK — naamgeving: dit document wordt in een dashboard getoond naast beide
plannen; de lezer weet niet wie 'ik' is. Schrijf daarom volledig in de derde
persoon: 'Claude: ...' en 'Codex: ...' (jij bent Codex). Nooit 'ik', 'mijn plan'
of 'het jouwe' in de uitvoer — ook niet in opsommingen bij conflicten.

Beknopt, concreet, Nederlands, markdown.

---
```

Daarna: opdracht, repo-context, `# Plan van Claude` (volledige inhoud),
`# Jouw eigen plan (ter referentie)` (codex-plan.md).

## 4. Claude-subagent — cross-review van Codex' plan (Agent-prompt)

```
Je hebt eerder een ontwikkelplan gemaakt (bijgevoegd pad). Een ander model
(Codex) maakte parallel een eigen plan voor dezelfde opdracht. Review dat plan:

Lees: <RUN_DIR>/plans/codex-plan.md (Codex) en <RUN_DIR>/plans/claude-plan.md (dat van jou).
Werkdirectory: <pwd> — toets beweringen aan de code, read-only.

Log je voortgang zoals eerder via log_event.py (--agent claude, zelfde RUN_DIR).

Schrijf je review naar <RUN_DIR>/plans/claude-review-of-codex.md:
1. 'Sterker in Codex' plan' (eerlijk — dit wordt overgenomen)
2. 'Zwakker in Codex' plan' (toets tegen de repo)
3. Koppen die beginnen met 'CONFLICT:' voor elke ONVERENIGBARE keuze, beide kanten neutraal beschreven
4. Eindoordeel: beste combinatie

BELANGRIJK — naamgeving: het document wordt in een dashboard getoond naast beide
plannen; de lezer weet niet wie 'ik' is. Schrijf volledig in de derde persoon:
'Claude: ...' en 'Codex: ...' (jij bent Claude). Nooit 'ik', 'mijn plan' of
'jouw plan' in de uitvoer — ook niet in opsommingen bij conflicten.

Meld je klaar met --type status --text done. Return: "REVIEW_KLAAR" + aantal conflicten.
```

## 5. Codex — validatie van de merge (`input/codex-validate-input.md`)

```
Hieronder staat een samengevoegd ontwikkelplan, gedestilleerd uit jouw eerdere
plan en dat van een ander model, inclusief door de gebruiker besliste keuzes.
Valideer de merge:

1. Is er iets wezenlijks uit Codex' oorspronkelijke plan (jouw eerdere plan)
   verloren gegaan dat erin hoorde?
2. Introduceert de combinatie nieuwe problemen (stappen die niet meer op elkaar aansluiten)?
3. Zijn de gebruikerskeuzes consequent doorgevoerd?

Antwoord kort. Begin met exact één regel: 'VERDICT: OK' of 'VERDICT: ISSUES'.
Daarna alleen bij ISSUES: de punten, concreet. Nederlands, derde persoon:
'Claude: ...' / 'Codex: ...' (jij bent Codex), nooit 'ik' of 'mijn'.

---
```

Daarna: het eindplan, de gebruikersbeslissingen (id + keuze + note), en een
verwijzing naar beide oorspronkelijke plannen (volledig bijvoegen).
