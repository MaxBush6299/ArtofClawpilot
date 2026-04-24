---
name: "orchestrator-outcome-validation"
description: "How Art of Clawpilot validates one publish-or-skip outcome per runDate and records reviewable skip metadata."
domain: "error-handling"
confidence: "high"
source: "earned"
tools:
  - name: "python"
    description: "Runs the hosted orchestrator entrypoint against real or fixture repo roots."
    when: "Use for fixture-backed publish, skip, and no-op validation runs."
---

## Context
Use this pattern when changing the hosted Python runner, persisted gallery contracts, or dry-run verification flow. The goal is to keep exactly one durable outcome per UTC `runDate` while making skipped days explicit and reviewable.

## Patterns
- Keep pre-run validation centralized in `orchestrator/validation.py`; validate config and persisted JSON before any model or git side effects.
- Resolve same-day idempotency from the gallery ledger during pre-run validation so reruns can exit cleanly as `publish`/`skip` no-ops.
- Validate post-run state in two layers: state-transition checks on the in-memory gallery model, then exact workspace write-set checks after persistence.
- Structured skip records should include top-level ledger fields plus nested `error` metadata; image-generation skips should also capture `creativeContext` from the curator brief, room, and reviewed prompt package.
- Keep fixture scenarios running through `python -m orchestrator.main` so dry-run proof and hosted logic share the same code path.
- When you need repeatable proof, clone the repo into disposable workspace checkouts, seed only the persisted gallery files needed to reach the target path, and assert a dry run leaves the checkout diff unchanged afterward.
- When acceptance requires role-specific negative coverage, confirm the fixture baseline can actually reach that role; an empty gallery needs a seeded sandbox or prior published image before Critic malformed-output scenarios count as covered.

## Examples
- `orchestrator/validation.py`: `validate_pre_run_state`, `validate_publish_state_transition`, `validate_publish_write_set`, `validate_skip_write_set`
- `orchestrator/main.py`: `build_skip_creative_context`, `build_skip_outcome`
- `orchestrator/contracts.py`: `SkipError`, `SkipRecord`
- `scripts/orchestrator_proof.py`: fixture matrix that seeds a prior image to force the Critic path, proves no-op reruns, and checks malformed-output / call-budget handling without touching the real repo state

## Anti-Patterns
- Do not add ad hoc skip writes outside the orchestrator validation flow.
- Do not treat image-generation skips as message-only records with no structured error or creative metadata.
- Do not validate only the JSON state while ignoring the actual file write set under `public/gallery/`.
