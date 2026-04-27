# Issue #16 Orchestrator Proof Extension Plan

> Status: Butters test scenarios to add after Kyle's implementation is complete
> Created: 2026-04-27

## Background

The existing `scripts/orchestrator_proof.py` provides deterministic dry-run validation for the orchestrator. It currently covers 8 scenarios for issue #15:

1. publish-happy-path
2. image-generation-failure
3. malformed-curator-output
4. malformed-critic-output
5. malformed-artist-review
6. artist-call-budget-overflow
7. already-resolved-no-op
8. corrupted-pre-run-gallery

## Extension Scenarios for Issue #16

Once Kyle's `runId` implementation is complete, extend `build_scenarios()` with the following multi-run proof scenarios:

### MR-1: Scheduled Run Idempotency (existing behavior preserved)
```python
Scenario(
    "scheduled-run-idempotency",
    "publish",
    seed_scheduled_run,  # Sets up runId=scheduled-2026-04-24
    0,
    validate_scheduled_idempotency
)
```
- Setup: First run with `--run-id scheduled-2026-04-24`
- Validation: Gallery has one image with `runId=scheduled-2026-04-24`
- Rerun: Same command exits `already_resolved` with 0 calls

### MR-2: Multi-Publish Same Day
```python
Scenario(
    "multi-publish-same-day",
    "publish",
    seed_multi_run_same_day,
    0,
    validate_multi_publish
)
```
- Setup: Two sequential runs with different `runId` values, same `runDate`
- First: `--run-id scheduled-2026-04-24`
- Second: `--run-id manual-2026-04-24-abc123`
- Validation: Gallery has two distinct images for `runDate=2026-04-24`, distinct `runId` values, distinct asset paths

### MR-3: Manual Run Idempotency
```python
Scenario(
    "manual-run-idempotency",
    "publish",
    seed_manual_run,
    0,
    validate_manual_idempotency
)
```
- Setup: First manual run with `--run-id manual-2026-04-24-xyz789`
- Rerun: Same `runId`
- Validation: Second run exits `already_resolved`, 0 model calls, no duplicate in gallery

### MR-4: Skip Closes Day
```python
Scenario(
    "skip-closes-day-for-manual",
    "skip-generation-failure",
    seed_skip_then_manual,
    0,
    validate_skip_blocks_manual
)
```
- Setup: First run creates skip record for `runDate=2026-04-24`
- Second: Manual run with different `runId`, same `runDate`
- Validation: Second run exits `day_already_closed`, 0 model calls, skip record has no `runId` field

### MR-5: Asset Path Collision Prevention
```python
Scenario(
    "asset-path-no-collision",
    "publish",
    seed_same_day_multi_run,
    0,
    validate_distinct_assets
)
```
- Setup: Two runs same day, similar titles
- Validation: Asset filenames include `runId` suffix, no collision in `public/gallery/{year}/`

### MR-6: Gallery Uniqueness Validation
```python
Scenario(
    "gallery-runid-uniqueness",
    "publish",
    seed_duplicate_runid_attempt,
    11,  # Hard fail on duplicate (runDate, runId)
    validate_duplicate_rejection
)
```
- Setup: Manually seed gallery with existing (`runDate`, `runId`) pair
- Run: Attempt publish with same composite key
- Validation: Orchestrator detects duplicate and exits cleanly (or hard fails if validation catches it at pre-run)

## Validation Helper Functions

### validate_scheduled_idempotency
```python
def validate_scheduled_idempotency(summary: dict) -> None:
    assert summary["outcome"] == "already_resolved"
    assert summary["curator_reasoning_calls"] == 0
    assert summary["artist_reasoning_calls"] == 0
    assert summary["image_generation_calls"] == 0
```

### validate_multi_publish
```python
def validate_multi_publish(summary: dict) -> None:
    gallery = load_gallery_state()
    images_for_date = [
        img for room in gallery.rooms 
        for img in room.images 
        if img.run_date == RUN_DATE
    ]
    assert len(images_for_date) == 2
    run_ids = {img.run_id for img in images_for_date}
    assert len(run_ids) == 2  # Distinct runId values
    assert "scheduled-2026-04-24" in run_ids
    assert "manual-2026-04-24-abc123" in run_ids
```

### validate_skip_blocks_manual
```python
def validate_skip_blocks_manual(summary: dict) -> None:
    assert summary["outcome"] == "day_already_closed"
    assert summary["curator_reasoning_calls"] == 0
    gallery = load_gallery_state()
    skip = next((s for s in gallery.skipped if s.run_date == RUN_DATE), None)
    assert skip is not None
    assert not hasattr(skip, "run_id")  # Skip has no runId
```

### validate_distinct_assets
```python
def validate_distinct_assets(summary: dict) -> None:
    gallery = load_gallery_state()
    images_for_date = [
        img for room in gallery.rooms 
        for img in room.images 
        if img.run_date == RUN_DATE
    ]
    paths = {img.path for img in images_for_date}
    assert len(paths) == len(images_for_date)  # All paths unique
    for img in images_for_date:
        assert img.run_id in img.path  # runId appears in asset filename
```

## Seed Helper Functions

### seed_scheduled_run
```python
def seed_scheduled_run(scenario_root: Path) -> None:
    # Empty gallery, will use --run-id scheduled-{RUN_DATE}
    pass
```

### seed_multi_run_same_day
```python
def seed_multi_run_same_day(scenario_root: Path) -> None:
    # Run orchestrator twice with different runId values
    # First: --run-id scheduled-2026-04-24
    # Second: --run-id manual-2026-04-24-abc123
    pass
```

### seed_skip_then_manual
```python
def seed_skip_then_manual(scenario_root: Path) -> None:
    # First run creates skip, second attempts manual with different runId
    pass
```

## Integration Notes

- Wait for Kyle to complete `--run-id` CLI arg implementation
- Wait for Kyle to update `resolve_existing_outcome(state, run_date, run_id)` signature
- Wait for Kyle to update `GalleryImageRecord` with `run_id` field
- After Kyle commits, extend `orchestrator_proof.py` with these scenarios
- Run `npm run orchestrator:proof` to verify all scenarios pass
- Document any failures or unexpected behavior

## Acceptance Criteria

All extended proof scenarios must pass before approving issue #16 closure. Each scenario validates:
- Correct idempotency behavior
- No duplicate records
- Proper asset path generation
- Skip-closes-day semantics preserved
- Log output shows expected `runId` values

## References

- Validation checklist: `docs/workspace/issue-16-validation-checklist.md`
- Existing proof script: `scripts/orchestrator_proof.py`
- Skill: `.squad/skills/multi-run-validation-gates/SKILL.md`
