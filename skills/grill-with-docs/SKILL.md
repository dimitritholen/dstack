---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, which also creates docs (ADRs and glossary) as we go.
disable-model-invocation: true
---

Call the Skill tool twice, for "grilling" and "domain-modeling".

## Sketch the structure questions

When a frontier question is about **the visual structure of a screen** — layout,
navigation, what sits where, or a moment of play in a game — don't describe the
options in prose. Draw them and let the user look.

- Copy [variants-template.html](./assets/variants-template.html) to
  `docs/sketches/<slug>-<screen>.html` (next to the `docs/adr/` domain-modeling
  writes), fill in every `{{PLACEHOLDER}}`, and build 2-4 variants from the
  primitives in [sketch-kit.html](./assets/sketch-kit.html). Three is the sweet
  spot. Copy the primitives; don't invent new ones per screen.
- Variants must differ **structurally, never cosmetically**: a different arrangement
  of the same content, not a restyling. One accent hue across all of them — a
  per-variant colour invites an answer about the wrong question.
- Open the file in the browser, then ask that round's question with `AskUserQuestion`
  using the **same letters and titles** as the cards.

This is only for screens and storyboards. A schema, a JSON payload, a config format,
a CLI signature or a state machine is a shape someone *reads* — put an ASCII sketch
inline in the question instead. That is far cheaper and it answers just as well.
