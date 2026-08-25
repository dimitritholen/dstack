# dstack

Dimitri Tholen's personal Claude Code plugin: the skills that survived a curation pass over two upstream repos, plus his own tools. Private by design; tailored to how he actually works (tasqx as the only tracker, few skills wired into real habits over broad suites).

Sources and adaptations are in [NOTICE.md](./NOTICE.md). One-time setup per repo: run `/setup-matt-pocock-skills` to configure the issue tracker and domain doc layout (answer with the real tracker: Linear or tasqx, never local markdown).

## User-invoked

Reachable only by typing the name.

- **[grill-with-docs](./skills/grill-with-docs/SKILL.md)**: relentless interview that sharpens a plan and leaves ADRs and a glossary behind. The usual entry point for non-trivial work.
- **[to-spec](./skills/to-spec/SKILL.md)**: turn the conversation into a spec, published to the issue tracker.
- **[to-tickets](./skills/to-tickets/SKILL.md)**: break a spec into tracer-bullet tickets in dependency order.
- **[implement](./skills/implement/SKILL.md)**: implement a spec or ticket (runs tdd and code-review internally).
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
- **[code-review](./skills/code-review/SKILL.md)**: review changes since a fixed point on standards and spec axes.
- **[resolving-merge-conflicts](./skills/resolving-merge-conflicts/SKILL.md)**: resolve an in-progress merge or rebase.
- **[prototype](./skills/prototype/SKILL.md)**: throwaway prototype to answer a design question.
- **[research](./skills/research/SKILL.md)**: investigate a question against primary sources, captured as Markdown.
- **[writing-for-agents](./skills/writing-for-agents/SKILL.md)**: how to write skills, AGENTS.md, and other agent-consumed docs.
- **[unslop](./skills/unslop/SKILL.md)**: cut AI tells from prose and add human voice.
- **[technical-writing](./skills/technical-writing/SKILL.md)**: layered standard for human-facing docs (Diátaxis, Google style, STE, Global English).
- **[duo-plan](./skills/duo-plan/SKILL.md)**: Claude and Codex plan the same task independently, then merge the best of both.

## Commands

- **/promptimize**: turn a rough prompt into an optimized one via interview; outputs only the final prompt.

## Install

```bash
claude plugin marketplace add dimitriofficial/dstack
claude plugin install dstack@dstack
```

The repo is its own single-plugin marketplace. After a `git pull` in a local checkout installed from the path, reinstall to pick up changes.
