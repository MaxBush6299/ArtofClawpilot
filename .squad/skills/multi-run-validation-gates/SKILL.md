---
name: "multi-run-validation-gates"
description: "Validation gates for supporting multiple executions per calendar day while preserving idempotency and skip-closes-day semantics."
domain: "testing"
confidence: "high"
source: "earned"
tools:
  - name: "powershell"
    description: "Runs local dry-run proofs with different requestId values for same runDate."
    when: "Testing duplicate request rejection, multi-publish same day, and retry-after-skip behavior."
---

## Context

Use this when the execution model shifts from one-outcome-per-day (single `runDate` identity) to multiple-outcomes-per-day (composite `runDate` + `requestId` identity). This pattern applies when:
- API-triggered manual runs need to coexist with scheduled runs
- Multiple images per calendar day are permitted
- Duplicate requests must be rejected idempotently
- Skip records still close the entire day (no retry after skip)

## Patterns

### Identity Model
- **Before:** Single `runDate` (YYYY-MM-DD) uniquely identifies each execution
- **After:** Composite (`runDate`, `requestId`) uniquely identifies each execution
- Published images store both `runDate` and `requestId`
- Skip records store only `runDate` (skip closes the day, no `requestId` needed)

### Resolution Logic (Three-Stage Check)
1. **Skip check:** If `runDate` has skip record → hard-stop, exit `day_already_closed`
2. **Duplicate check:** If (`runDate`, `requestId`) already published → idempotent no-op
3. **Proceed:** Otherwise → execute roles and publish

### Validation Gates
Split validation into **scheduler safety** and **manual multi-run safety**:

**Scheduler Safety:**
- Scheduled run at 00:05 UTC publishes successfully
- Manual API run at 14:30 UTC same day publishes independently (no false collision)
- Both images coexist in gallery for same `runDate`

**Manual Multi-Run Safety:**
- Same `requestId` retry → idempotent `already_resolved` with zero model calls
- Different `requestId` same day → new independent publish
- Concurrent API calls → both complete without gallery corruption
- Git push conflict → rebase retry succeeds

**Skip-Closes-Day:**
- First execution fails → writes skip record to `skipped[]`
- Second execution (any `requestId`) → detects skip, exits `day_already_closed` before any model call
- No retry allowed after skip (skip is terminal for that calendar day)

### Acceptance Test Matrix

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| MR-1 | Duplicate request (same `requestId`) | `already_resolved`, 0 calls | Makes model calls |
| MR-2 | Different request same day | Both publish | Second skips |
| MR-3 | Scheduled + manual same day | Both publish | Collision |
| MR-4 | Skip then retry | `day_already_closed`, 0 calls | Proceeds |
| MR-5 | Concurrent API calls | Both publish | Corruption |
| MR-6 | Git push conflict | Rebase succeeds | Retry fails |
| MR-7 | Frontend multi-runDate | Renders correctly | Crashes |
| MR-8 | Log correlation | Distinct per request | Conflated |

### Local Dry-Run Commands
```bash
# Duplicate request rejection
python -m orchestrator.main --run-date 2099-02-20 --request-id abc123 --use-fixtures
python -m orchestrator.main --run-date 2099-02-20 --request-id abc123 --use-fixtures
# Expected: second exits already_resolved with zero calls

# Multi-publish same day
python -m orchestrator.main --run-date 2099-02-20 --request-id req-1 --use-fixtures
python -m orchestrator.main --run-date 2099-02-20 --request-id req-2 --use-fixtures
# Expected: both publish successfully, gallery has two images for 2099-02-20

# Retry after skip
python -m orchestrator.main --run-date 2099-02-21 --request-id skip-1 --fixture-scenario skip-generation-failure
python -m orchestrator.main --run-date 2099-02-21 --request-id skip-2 --use-fixtures
# Expected: second exits day_already_closed with zero calls
```

### Hosted Smoke Extension (Phase B/C)
Extend existing smoke checklist phases to cover multi-run:

**Phase B-Extended:**
1. Publish with `runDate=2099-03-01`, `requestId=smoke-req-1`
2. Rerun same `runDate` + `requestId` → verify `already_resolved` log
3. Run same `runDate`, different `requestId=smoke-req-2` → verify second publish lands

**Phase C-Extended:**
1. Skip scenario with `runDate=2099-03-02`, `requestId=smoke-skip-1`
2. Retry same `runDate`, different `requestId=smoke-skip-2` → verify `day_already_closed` log

### Gallery Validation Rules (Extended)
- Each image record must have `runDate` (YYYY-MM-DD) and `requestId` (non-empty string)
- (`runDate`, `requestId`) pairs must be unique across all images
- `runDate` can appear multiple times (with different `requestId` values)
- Skip records remain `runDate`-only (no `requestId` field)
- No image and skip record may share the same `runDate`

### Concurrency Handling
- **Gallery JSON writes:** Use git pull-rebase-push pattern with retry on conflict
- **Asset filenames:** Extend to `YYYY-MM-DD-{slug}-{requestId-suffix}.png` to avoid collision
- **Log correlation:** Include `requestId` in every log phase for troubleshooting

## Examples

### Example 1: Duplicate Request Rejection
```python
# orchestrator/validation.py
def resolve_existing_outcome(state: GalleryState, run_date: str, request_id: str) -> str | None:
    # Check skip first (closes entire day)
    for skip in state.skipped:
        if skip.run_date == run_date:
            return "skip"  # day_already_closed
    
    # Check for duplicate (runDate, requestId)
    for room in state.rooms:
        for image in room.images:
            if image.effective_run_date() == run_date and image.request_id == request_id:
                return "publish"  # already_resolved
    
    return None  # proceed with execution
```

### Example 2: Multi-Publish Same Day
```json
// data/gallery.json after two runs same day
{
  "rooms": [
    {
      "id": "room-01",
      "images": [
        {
          "id": "img-20260427-1",
          "runDate": "2026-04-27",
          "requestId": "scheduled-20260427",
          "title": "Morning Light"
        },
        {
          "id": "img-20260427-2",
          "runDate": "2026-04-27",
          "requestId": "manual-api-xyz789",
          "title": "Evening Shadow"
        }
      ]
    }
  ]
}
```

### Example 3: Skip Closes Day
```json
// data/gallery.json after skip
{
  "skipped": [
    {
      "id": "skip-20260428",
      "runDate": "2026-04-28",
      "stage": "artist",
      "reasonCode": "malformed_output"
    }
  ]
}
// Any retry for runDate=2026-04-28 exits day_already_closed
```

## Anti-Patterns

- Do not allow retry after skip—skip is terminal for that calendar day.
- Do not assume `runDate` uniqueness in gallery; always check (`runDate`, `requestId`).
- Do not skip concurrency testing—gallery JSON corruption is a real risk.
- Do not conflate log traces across multiple `requestId` values—each must be independently traceable.
- Do not defer git push retry logic—conflict is expected in rapid multi-run scenarios.
- Do not assume frontend handles multi-`runDate` entries safely—explicit review required.

## References

- `workspace/multi-run-testing-gates.md` (full specification)
- `docs/architecture/hosted-validation-gates.md` (current one-per-day contract)
- `orchestrator/validation.py` (`resolve_existing_outcome()` function)
