---
description: Show the dstack skills and where each one sits in the development cycle
---

Print the block below verbatim as your entire reply. Do not call any tool, do not
add a preamble, do not summarise it afterwards.

If `$ARGUMENTS` names one of the skills, print the block first, then add one line:
what that skill does and how it is invoked (user-invoked skills are typed by name;
model-invoked ones fire on their own).

---

**dstack** — 21 skills. The cycle runs setup → design → spec → tickets → implement → retro.

| # | Phase | Skills |
|---|-------|--------|
| 0 | Repo setup (once) | `setup-matt-pocock-skills` |
| 1 | Explore / sharpen | `grill-with-docs` (user-invoked) ← `grilling`, `research`, `prototype`, `duo-plan`, `domain-modeling` |
| 2 | Spec | `to-spec` |
| 3 | Breakdown | `to-tickets` |
| 4 | Build | `implement` ← `tdd`, `codebase-design`, `review-vs-spec` |
| 5 | Close session | `retro` |
| — | Cross-cutting, on demand | `wayfinder` + `handoff` (work > 1 session), `diagnosing-bugs`, `resolving-merge-conflicts` |
| — | Prose support | `technical-writing`, `unslop`, `writing-for-agents` |

User-invoked (type the name): `setup-matt-pocock-skills`, `grill-with-docs`, `to-spec`,
`to-tickets`, `implement`, `wayfinder`, `handoff`, `retro`. The rest fire on their own.

Commands: `/dstack:promptimize`, `/dstack:help`.

Not covered by this plugin: anything after the commit — PR, merge, release, changelog,
CI-failure loop. General bug-hunt review is the built-in `/code-review`.
