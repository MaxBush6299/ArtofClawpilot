---
name: "frontend-contract-review"
description: "Review frontend-facing contract docs by cross-checking smoke-proof claims against the actual pages, data ledger shape, and producer validation rules."
domain: "testing"
confidence: "high"
source: "earned"
---

## Context

Use this when a doc or review claims the frontend already tolerates new gallery ledger fields. The goal is to confirm the guidance matches the real repo behavior, not just the intended architecture.

## Patterns

- Check the consuming pages (`src/pages/Home.tsx`, `src/pages/Room.tsx`) and the producing contract (`orchestrator/validation.py`, `orchestrator/main.py`) together before approving docs.
- Distinguish producer guarantees from frontend tolerance. A field can be required for new publishes but still irrelevant to current rendering.
- Treat exact formats as part of the contract. In this repo, `runDate` is a `YYYY-MM-DD` string, not a full ISO timestamp.
- Reject smoke-proof steps that assume a UI outcome the code does not guarantee. In this repo, `Home.tsx` uses `r.images?.[0]` while the orchestrator appends new images, so “new publish becomes cover” is not a stable assertion.
- Reject claims that static JSON imports equal schema validation when the consuming code still uses `any` and no explicit validator exists.

## Examples

- `src/pages/Home.tsx`: room cards render from `gallery.rooms` and use `r.images?.[0]` for the cover.
- `src/pages/Room.tsx`: room detail renders `img.id`, `img.path`, `img.title`, `img.artistNote`, optional `img.criticism`, and `img.createdAt`.
- `orchestrator/main.py`: `apply_publish_outcome` appends new images to `target_room.images`.
- `orchestrator/validation.py`: `run_date must be YYYY-MM-DD` and new images must include `promptSummary`, `model`, and `reasoningModel`.

## Anti-Patterns

- Do not approve a frontend guide just because the general architecture sounds right.
- Do not label current code as using optional chaining, schema validation, or newest-first ordering unless the source actually does that.
- Do not turn smoke proof into a brittle UI script with room-count or cover-image assumptions that only hold for today's seed data.
