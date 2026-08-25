---
name: retro
description: "Conduct a retrospective on a coding session."
disable-model-invocation: true
---

The user has asked for a **retrospective**. You are suggesting improvements to the coding agent's **environment** to improve future runs.

## Steps

1. Call the Skill tool with `writing-for-agents` for the writing style guide.

2. Locate the primary sources for the session the user specifies. This may mean searching through session logs on this machine. If the user doesn't specify a session, default to the current one.

3. Fan out three read-only reviewer subagents over the transcript in parallel, one lens each. Every reviewer gets the transcript path, the category list below, and returns findings only; the parent applies edits, reviewers never write.

- **Judgment**: where did the agent choose an approach, and was it the right one? Wrong turns, corrections from the user, dead ends before the working path.
- **Tooling**: which tool calls were expensive, repeated, or avoidable? Checks that would have caught a mistake, friction in the environment.
- **Divergent**: what nearly went wrong, and what information was missing when it was needed?

Each finding names a category from the Categories reference below, the transcript moment that supports it, and the improvement it suggests.

4. Synthesize. Deduplicate findings across reviewers (two lenses reporting the same moment is one finding, and higher-confidence for it), then sort every finding into three buckets:

- **Accepted**: a real, recurring improvement with transcript evidence.
- **Backlog**: legitimate but not worth an edit now, or needing work beyond a steering change.
- **Rejected**: a one-off, or already covered by an instruction the agent followed correctly.

Before presenting, run a structural check on the Accepted list: any lesson that a lint rule, test, script, or check would enforce more reliably than prose routes to that automated check, never to a steering file. Prose rules drift; checks don't.

5. Give every Accepted finding a routing, the concrete edit it becomes:

- a **navigation pointer** in `CLAUDE.md`/`AGENTS.md`
- a rule in `CODING_STANDARDS.md`
- an **automated check** (lint, test, script)
- an edit to an existing skill, or a new skill, written per the `writing-for-agents` skill
- a tooling change (CLI, MCP, log access)

6. Present the full Accepted / Backlog / Rejected output to the user, in order of severity, with each Accepted finding's routing. Steering changes affect every future session, so wait for explicit approval and apply only the subset the user picks. Include the Rejected list with a one-line reason each, so the user can override the filter.

## Reference

### Categories

Reviewers tag every finding with one of these.

- **Navigation**: how easy was it for the agent to find the right files? Are there hidden dependencies between files? Would a **navigation pointer** make it easier? _Use when_ the session took a long time to find a piece of information.
- **Automated checks**: are there automated checks that could catch errors the agent made? Linting, typing, tests, filesystem linters? _Use when_ the agent made a mistake that could have been caught by an automated check.
- **Coding standards**: should the **reviewer agent** be given a new rule to enforce? Should an existing rule be removed or clarified? _Use when_ the reviewer agent failed to catch a mistake.
- **Global AGENTS.md**: are there any steering instructions that should be moved to coding standards (or automated checks) instead? _Use when_ the AGENTS.md file is particularly large - in the repo OR the user's global scope.
- **Tool economy**: did the agent make expensive tool calls that could be streamlined? Is there any custom tooling (CLI's, MCP's) that is particularly token-inefficient? _Use when_ the agent made an expensive tool call.
- **No-ops**: look for instructions in steering files that don't modify the agent's behavior. _Use when_ the steering files are large and unwieldy.
- **Information access**: look for opportunities to increase the agent's access to information. Teeing dev server logs, readonly access to third-party services. _Use when_ a crucial piece of information was not available to the agent.

### Implementation vs Review

Remember that all work goes through two stages: implementation and review. The implementation agent has the most **context pressure**. They are responsible for exploration, writing code, and debugging failures.

The review agent has the least context pressure - it receives a diff, so no exploration needed. It often does not need to write code or debug.

This means that the review agent should be responsible for imposing coding standards, not the implementation agent.

### Files

You have access to several files in the repo:

- `CLAUDE.md`/`AGENTS.md`: these files are pushed to the context window of any agent working in this repo. They should be used incredibly sparingly, usually only for **navigation pointers** to other files.
- `CODING_STANDARDS.md`: this file is read during review, not implementation. Add **navigation pointers** to docs folders if the standards file gets more than 1,000 lines long.
- Docs: use docs as references files, pointed to by other files. Look for existing docs before writing new ones.
- Skills: use skills for docs (since their description goes into the agent's context window), or for user-invoked commands. Follow the advice in the `writing-for-agents` skill.
