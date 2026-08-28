# dstack

Dimitri Tholen's personal Claude Code plugin: the skills that survived a curation pass over two upstream repos, plus his own tools. Private by design; tailored to how he actually works (tasqx as the only tracker, few skills wired into real habits over broad suites).

Sources and adaptations are in [NOTICE.md](./NOTICE.md).

## Getting started

Prerequisites:

- **tasqx** (or Linear) reachable from the repo you work in. The pipeline skills publish specs and tickets to an issue tracker; the setup skill offers local markdown, but the house rule is to always answer with the real tracker.
- **OpenAI Codex CLI** on PATH, only if you want [duo-plan](./skills/duo-plan/SKILL.md).

Install:

```bash
claude plugin marketplace add dimitritholen/dstack
claude plugin install dstack@dstack
```

The repo is its own single-plugin marketplace. After a `git pull` in a local checkout installed from the path, reinstall to pick up changes.

Then, once per repo you use the pipeline in, run `/setup-matt-pocock-skills`. It configures the issue tracker, triage labels, and domain doc layout the engineering skills assume; skipping it leaves the pipeline skills guessing.

A typical first feature runs through the pipeline in order:

1. `/grill-with-docs` to stress-test the idea; sketches the screen-layout options so you pick by looking; leaves ADRs and a glossary behind.
2. `/to-spec` to turn that conversation into a spec in the tracker.
3. `/to-tickets` to break the spec into tracer-bullet tickets in dependency order.
4. `/implement` per ticket; it runs tdd and review-vs-spec internally.
5. `/retro` at the end of a session to mine the transcript for environment improvements.

For work too big for one session, `/wayfinder` plans it as a shared map of decision tickets, and `/handoff` compacts the conversation for the next agent. Everything under Model-invoked below fires on its own when the situation matches; you never need to invoke those by hand.

## User-invoked

Reachable only by typing the name.

- **[grill-with-docs](./skills/grill-with-docs/SKILL.md)**: relentless interview that sharpens a plan and leaves ADRs and a glossary behind. The usual entry point for non-trivial work.
- **[to-spec](./skills/to-spec/SKILL.md)**: turn the conversation into a spec, published to the issue tracker.
- **[to-tickets](./skills/to-tickets/SKILL.md)**: break a spec into tracer-bullet tickets in dependency order.
- **[implement](./skills/implement/SKILL.md)**: implement a spec or ticket (runs tdd and review-vs-spec internally).
- **[wayfinder](./skills/wayfinder/SKILL.md)**: plan work too big for one session as a shared map of decision tickets.
- **[handoff](./skills/handoff/SKILL.md)**: compact the conversation into a handoff document for the next agent.
- **[retro](./skills/retro/SKILL.md)**: session retrospective; parallel reviewers mine the transcript for environment improvements, each accepted finding routed to a concrete edit.
- **[setup-matt-pocock-skills](./skills/setup-matt-pocock-skills/SKILL.md)**: one-time per-repo configuration for the pipeline skills.

## Model-invoked

Fire on their own when the situation matches; typing the name also works.

- **[grilling](./skills/grilling/SKILL.md)**: the interview primitive behind grill-with-docs.
- **[domain-modeling](./skills/domain-modeling/SKILL.md)**: build and sharpen a project's domain model (CONTEXT.md, ADRs).
- **[codebase-design](./skills/codebase-design/SKILL.md)**: shared vocabulary for deep modules, seams, and interfaces.
- **[diagnosing-bugs](./skills/diagnosing-bugs/SKILL.md)**: diagnosis loop for hard bugs and regressions.
- **[tdd](./skills/tdd/SKILL.md)**: red-green-refactor with integration-first tests.
- **[review-vs-spec](./skills/review-vs-spec/SKILL.md)**: review changes since a fixed point on standards and spec axes (renamed from code-review to avoid colliding with the built-in skill).
- **[resolving-merge-conflicts](./skills/resolving-merge-conflicts/SKILL.md)**: resolve an in-progress merge or rebase.
- **[prototype](./skills/prototype/SKILL.md)**: throwaway prototype to answer a design question.
- **[research](./skills/research/SKILL.md)**: investigate a question against primary sources, captured as Markdown.
- **[writing-for-agents](./skills/writing-for-agents/SKILL.md)**: how to write skills, AGENTS.md, and other agent-consumed docs.
- **[unslop](./skills/unslop/SKILL.md)**: cut AI tells from prose and add human voice.
- **[technical-writing](./skills/technical-writing/SKILL.md)**: layered standard for human-facing docs (Diátaxis, Google style, STE, Global English).
- **[duo-plan](./skills/duo-plan/SKILL.md)**: Claude and Codex plan the same task independently, then merge the best of both.

## Commands

- **/dstack:help**: the skill map — every skill and where it sits in the development cycle.
- **/dstack:promptimize**: turn a rough prompt into an optimized one via interview; outputs only the final prompt.
