---
name: "multi-run-idempotency"
description: "Design pattern for supporting multiple execution runs per time period without duplicates or ambiguous reruns."
domain: "architecture"
confidence: "high"
source: "earned"
tools:
  - name: "python"
    description: "Implements idempotency checks, unique ID generation, and validation logic."
    when: "When orchestrator needs to support multiple runs per day with distinct outcomes."
---

## Context
Use this pattern when extending a "one outcome per time period" system to support multiple runs (scheduled + on-demand) while preserving idempotency, avoiding duplicates, and maintaining clear audit trails.

## Patterns
- Introduce composite run identifier (`runId`) as primary idempotency key, distinct from time-based key (`runDate`).
- Format `runId` as `{timeKey}-{source}-{sequence}` for human-readable logs and git history (e.g., `2026-04-27-scheduled-01`, `2026-04-27-manual-02`).
- Keep time-based key (`runDate`) as secondary index for day-level queries and rate limiting.
- Generate unique outcome identifiers (`imageId`, `skipId`) independent of run instance, with collision detection.
- Idempotency check: exact `runId` match → no-op; new `runId` same time period → new outcome allowed.
- File naming: support collision suffixes (`-02`, `-03`) when multiple outcomes share base name.
- Atomic commits: one git commit per successful outcome, including `runId` in message for traceability.
- Structured logging: include `runId`, `triggerSource`, `runDate` in all events for correlation.
- API retry: same `runId` retry → idempotent no-op; new trigger → new `runId` → new attempt.
- Backward compatibility: make new fields optional initially, backfill defaults for existing records.

## Examples
- `orchestrator/contracts.py`: Add `runId`, `triggerSource` fields to `GalleryImageRecord`, `SkipRecord`
- `orchestrator/validation.py`: Update `resolve_existing_outcome(run_id)` to check `runId` exact match
- `orchestrator/main.py`: Generate `runId` from env or CLI args, include in all JSONL events
- API route: `POST /api/trigger-run` generates unique `runId`, queues job with run context
- Git commits: Include `[runId]` in commit message for audit trail

## Anti-Patterns
- Using time-based key alone as idempotency check (breaks multi-run support)
- Allowing `runId` collisions across different trigger sources
- Omitting `runId` from logs or git commits (loses traceability)
- Reusing same `runId` for retry after failure (breaks idempotent no-op contract)
- Skipping collision detection for outcome identifiers (risks overwriting existing data)

## Migration Strategy
1. **Phase 1 (backward compatible):** Add optional `runId` field, generate internally if missing, update idempotency to prefer `runId` when present
2. **Phase 2 (feature expansion):** Add API route to trigger new runs, generate unique `runId` per invocation
3. **Phase 3 (enforcement):** Make `runId` required, enforce uniqueness validation, update frontend to display run metadata

## Related Patterns
- See `orchestrator-outcome-validation` for one-outcome-per-period validation
- See `contract-first-model-calls` for bounded workflows with typed outcomes
