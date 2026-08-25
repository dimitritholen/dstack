# Provenance

Every skill in this repo was copied on 2026-08-25 from one of three sources and is maintained here independently from then on.

## mattpocock/skills (MIT, Copyright (c) 2026 Matt Pocock)

Copied from a local clone of https://github.com/mattpocock/skills at commit `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`:

code-review, codebase-design, diagnosing-bugs, domain-modeling, grill-with-docs, grilling, handoff, implement, prototype, research, resolving-merge-conflicts, setup-matt-pocock-skills, tdd, to-spec, to-tickets, wayfinder, writing-for-agents.

Copied verbatim. The excluded `triage` skill is a clean seam: `setup-matt-pocock-skills` detects its absence and skips its section.

## pstack (MIT, Copyright (c) 2026 Lauren Tan)

Adapted from the pstack plugin in https://github.com/cursor/plugins (`plugins/pstack/skills/`), via the ports first made in the clone above:

- `unslop`: em-dash rule aligned with Dimitri's rewrite guidance (parentheses allowed); model-invoked description rewritten.
- `technical-writing`: flipped to model-invoked; unslop dependency phrased as a Skill tool call; pstack-specific tab-indent rule dropped.

Each carries its own `NOTICE.md` with the full MIT text.

The `retro` skill is Dimitri's own, with its reviewer fan-out, Accepted/Backlog/Rejected synthesis, and routing step adapted from pstack's `reflect`.

## Dimitri's own

- `duo-plan` (skill), `promptimize` (command), `retro` (skill, see above).
