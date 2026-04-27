---
name: "learning-doc-author"
description: "Produce tutorial-style, hands-on learning documents that teach a concept by having the reader build or modify code. Output goes to docs/learning/<topic>.md."
domain: "documentation, education, onboarding"
confidence: "high"
source: "manual"
tools: []
---

## Context

Use this skill when the user wants to **teach** something using the codebase —
onboarding new devs, explaining a pattern that recurs in the project, or
walking through a concept (e.g. dependency injection, retry policies, queue
fan-out) as it's used here.

Style is **tutorial / learn-by-doing**: the reader follows guided exercises
with checkpoints. They aren't just reading prose — they're typing, running,
and inspecting output.

If the topic touches Microsoft/Azure technology, **delegate citations to the
`ms-docs-grounding` skill** for the conceptual background, then ground the
hands-on parts in the actual codebase.

## Patterns

### Output location and naming

- Write learning docs to `docs/learning/<kebab-case-topic>.md` in the target
  repo. Create the folder if missing.
- One topic per file. Long topics may split into a numbered series
  (`docs/learning/<topic>-01-intro.md`, `-02-...`).

### Required sections (in this order)

```markdown
# Learn: <Topic>

> One-paragraph summary of what you'll learn and why it matters in this codebase.

## Audience & Goal

> Default audience: the solution engineer maintaining or onboarding to this
> codebase (you, or a teammate). Voice is internal/dev-honest. If the doc will
> later be re-shaped for customers, capture the "adapt for customer" notes at
> the end rather than softening the body.

## Learning Objectives
By the end of this tutorial you will be able to:
- <verb-led objective 1>
- <verb-led objective 2>
- <verb-led objective 3>

## Prerequisites
- What the reader should already know.
- What they need installed/configured.
- Estimated time.

## Concepts (just enough)
Short conceptual primer — only the minimum needed to attempt the exercises.
Link out for deeper background; cite Microsoft Learn pages where relevant.

## Exercise 1 — <what they'll build/change>

**Goal:** one sentence.

**Steps:**
1. ...
2. ...
3. ...

**Code-along:**
```<lang>
<code the reader writes or pastes>
```

**Run it:**
```bash
<command>
```

**Checkpoint:** What you should see, AND a self-check question
("Why does the call fail if you skip step 2?").

## Exercise 2 — ...
(repeat — each exercise builds on the previous one)

## What You Learned
- Recap each objective with the line of code or behavior that proved it.
- "If you got stuck on X, re-read the Concepts section."

## Going Deeper
- Pointers to advanced patterns in this codebase.
- External references (Microsoft Learn, RFCs, etc.) with dates.

## Adapt for a Customer Audience
- 3-5 bullets: what to omit (debug paths, internal naming), what to
  emphasize, what concept-level slides could be derived from this tutorial.

## Solutions
Collapsed/expandable answers to checkpoint questions, so the reader can
self-verify without spoiling the exercise.
```

### Pedagogical rules

- **Active over passive.** Every exercise has the reader *do* something
  observable, not just read.
- **Build incrementally.** Each exercise should depend on the previous one,
  ending in a small working artifact.
- **Checkpoints with self-checks.** Don't just say "you should see X" — also
  ask a question that proves they understood *why*.
- **Cognitive load.** Introduce one new concept per exercise. If you need two,
  split into two exercises.
- **Show the failure paths.** A great tutorial deliberately walks the reader
  through a wrong turn so they recognize the symptom later.

### Voice

Encouraging, second-person, no condescension. It's fine to say "this part is
tricky" — that's honest. Avoid "simply", "just", "obviously".

### Grounding

- Every claim about the **codebase** must be verified by reading the actual
  source. Reference real files and line ranges.
- Every claim about **Microsoft/Azure technology** must be grounded via the
  `ms-docs-grounding` skill, with dated citations.

## Examples

A request like *"Write a learning doc on how this project uses MediatR"*
should produce `docs/learning/mediatr-in-this-project.md` with:
- objectives like "trace a command from controller to handler",
- a concepts section citing the MediatR docs with date,
- exercises that have the reader add a new command + handler,
- checkpoints that fail loudly if they wired it up wrong,
- a solutions section at the end.

## Anti-Patterns

- ❌ Pure prose with no code-along. (That's a reference doc, not a tutorial.)
- ❌ Exercises that don't build on each other.
- ❌ "Hello world" examples that don't reflect how the codebase actually uses
  the concept.
- ❌ Checkpoints that just say "you should see output" without a self-check
  question.
- ❌ Dumping all prerequisites at the end instead of the top.
- ❌ Skipping the **Solutions** section — readers need to self-verify.
- ❌ Skipping the **Adapt for a Customer Audience** section — the SE re-uses
  this material with customers and needs the safety bullets.
