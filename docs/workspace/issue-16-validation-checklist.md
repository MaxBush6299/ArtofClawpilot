# Issue #16 Run Identity Refactor - Validation Checklist

> Status: Butters acceptance gates for run identity refactor implementation
> Issue: #16 https://github.com/MaxBush6299/ArtofClawpilot/issues/16
> Created: 2026-04-27

## Overview

This checklist defines the acceptance criteria for shifting from day-scoped idempotency (`runDate` alone) to run-scoped idempotency (composite `runDate` + `runId`/`requestId`). The goal: support multiple intentional same-day executions while preventing duplicate retries.

## Core Contract Changes

### Identity Model Shift
- **Before:** Single `runDate` (YYYY-MM-DD) uniquely identifies execution
- **After:** Composite (`runDate`, `runId`) uniquely identifies execution
- **Scheduled runs:** `runId = scheduled-{runDate}` (one per day)
- **Manual runs:** `runId = manual-{runDate}-{uuid}` (multiple per day allowed)

### Resolution Logic (Three-Stage Check)
1. **Skip check:** If `runDate` has skip record → hard-stop, exit `day_already_closed`
2. **Duplicate check:** If (`runDate`, `runId`) already published → idempotent no-op
3. **Proceed:** Otherwise → execute roles and publish

### Data Shape Evolution
- `GalleryImageRecord` gains `runId` field (optional initially for backward compat)
- Skip records remain `runDate`-only (skip closes entire day)
- Asset paths include `runId` to prevent same-day collision
- Log phase emits `runId` for trace correlation

## Acceptance Test Matrix

### Category 1: Scheduled Run Safety
Ensure the daily scheduler remains idempotent and does not break existing behavior.

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **SR-1** | Scheduled run publishes | Creates `runId=scheduled-{runDate}`, publishes successfully | Fails or uses wrong ID format |
| **SR-2** | Same-day scheduled retry | Exits `already_resolved`, 0 model calls, no second commit | Makes model calls or writes |
| **SR-3** | Scheduled run after prior scheduled publish | Detects prior `scheduled-{runDate}`, exits cleanly | Creates duplicate |

### Category 2: Manual Run Safety
Validate that manual-triggered runs can coexist with scheduled runs.

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **MR-1** | Manual run same day as scheduled | Both publish, distinct `runId` values, distinct commits | Collision or false duplicate |
| **MR-2** | Second manual run same day | Both publish, distinct `runId` values | Second skips |
| **MR-3** | Manual retry (same `runId`) | Exits `already_resolved`, 0 calls | Makes model calls |
| **MR-4** | Manual run different `runId` same day | Publishes successfully | False duplicate detected |

### Category 3: Skip-Closes-Day Enforcement
Ensure skip records still close the entire calendar day.

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **SK-1** | Skip then scheduled retry | Exits `day_already_closed`, 0 calls | Proceeds with generation |
| **SK-2** | Skip then manual run | Exits `day_already_closed`, 0 calls | Proceeds with generation |
| **SK-3** | Skip record created correctly | Has `runDate` only (no `runId` field) | Includes `runId` |

### Category 4: Asset and Record Collision Prevention

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **AC-1** | Two runs same day | Distinct asset filenames (include `runId` suffix) | Filename collision |
| **AC-2** | Gallery JSON uniqueness | No duplicate (`runDate`, `runId`) pairs | Duplicate pairs exist |
| **AC-3** | Asset path validation | Paths match `YYYY/YYYY-MM-DD-{slug}-{runId-suffix}.png` | Wrong pattern |

### Category 5: Frontend Tolerance

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **FT-1** | Multiple images same `runDate` | Frontend renders both without crash | Crashes or fails build |
| **FT-2** | Gallery with `runId` field | Frontend reads `runId` (optional field tolerance) | Build breaks |
| **FT-3** | Frontend build passes | `npm run build` exits 0 after gallery update | Build fails |

### Category 6: Log Correlation

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **LC-1** | Scheduled run logs | All phases show `runId=scheduled-{runDate}` | Missing `runId` |
| **LC-2** | Manual run logs | All phases show `runId=manual-{runDate}-{uuid}` | Missing `runId` |
| **LC-3** | Concurrent runs | Distinct `traceId` and `runId` per execution | Logs conflated |

### Category 6B: Backward Compatibility and Legacy Preservation

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **BC-1** | Existing pre-runId images in gallery | All existing images preserved in gallery.json after new publish | Any existing image removed |
| **BC-2** | Legacy image effective_run_id() | Pre-runId images return fallback `id` value | Returns None or crashes |
| **BC-3** | Mixed gallery rendering | Frontend displays both legacy (no runId) and new (with runId) images | Crashes or filters out legacy |
| **BC-4** | Gallery array append behavior | New images appended to room.images[], not replacing array | Existing images overwritten |

### Category 7: Hosted Deployment Gate (End-to-End Close Gate)

| Test | Scenario | Expected Outcome | Rejection If... |
|------|----------|------------------|-----------------|
| **HG-1** | Deploy refactored code | ACA Job deploys successfully, bootstrap starts | Deploy fails |
| **HG-2** | Scheduled execution on main | Publishes with `runId=scheduled-{runDate}`, commits to main | Fails or wrong ID |
| **HG-3** | Generate gallery image | New image added to `data/gallery.json`, asset in `public/gallery/` | No image or asset missing |
| **HG-4** | Log Analytics proof | Logs show complete phase progression with `runId` | Missing logs or `runId` |

## Local Dry-Run Commands

### Baseline Proof (Existing Behavior Preserved)
```bash
# Scheduled run - first execution
python -m orchestrator.main --run-date 2099-03-10 --use-fixtures --fixture-scenario publish

# Scheduled run - retry same day (should no-op)
python -m orchestrator.main --run-date 2099-03-10 --use-fixtures --fixture-scenario publish
# Expected: logs show already_resolved, 0 model calls, no new commit
```

### Multi-Run Proof (New Behavior)
```bash
# Scheduled run
python -m orchestrator.main --run-date 2099-03-11 --run-id scheduled-2099-03-11 --use-fixtures --fixture-scenario publish

# Manual run same day (should publish)
python -m orchestrator.main --run-date 2099-03-11 --run-id manual-2099-03-11-abc123 --use-fixtures --fixture-scenario publish
# Expected: second run publishes successfully, gallery has two images for 2099-03-11

# Manual retry (should no-op)
python -m orchestrator.main --run-date 2099-03-11 --run-id manual-2099-03-11-abc123 --use-fixtures --fixture-scenario publish
# Expected: logs show already_resolved, 0 model calls, no duplicate
```

### Skip-Closes-Day Proof
```bash
# First run fails and creates skip
python -m orchestrator.main --run-date 2099-03-12 --run-id scheduled-2099-03-12 --use-fixtures --fixture-scenario skip-generation-failure

# Manual retry after skip (should exit day_already_closed)
python -m orchestrator.main --run-date 2099-03-12 --run-id manual-2099-03-12-xyz789 --use-fixtures --fixture-scenario publish
# Expected: logs show day_already_closed, 0 model calls, no publish
```

## Validation.py Expected Changes

### New Function Signature
```python
def resolve_existing_outcome(
    state: GalleryState, 
    run_date: str, 
    run_id: str
) -> str | None:
    # Check skip first (closes entire day)
    for skip in state.skipped:
        if skip.run_date == run_date:
            return "skip"  # day_already_closed
    
    # Check for duplicate (runDate, runId)
    for room in state.rooms:
        for image in room.images:
            if image.run_date == run_date and image.run_id == run_id:
                return "publish"  # already_resolved
    
    return None  # proceed with execution
```

### Updated Validation Rules
- `validate_gallery_state()`: Check uniqueness of (`runDate`, `runId`) pairs
- `validate_existing_image_record()`: Verify `runId` field present (optional for legacy)
- `validate_skip_record()`: Ensure skip has `runDate` only (no `runId`)
- Asset path validation: Match `YYYY/YYYY-MM-DD-{slug}-{runId-suffix}.png`

## Contracts.py Expected Changes

### GalleryImageRecord
```python
@dataclass
class GalleryImageRecord:
    id: str
    title: str
    path: str
    created_at: str
    prompt_summary: str
    artist_note: str
    run_date: str
    run_id: str | None = None  # New field, optional for backward compat
    model: str | None = None
    criticism: str | None = None
    reasoning_model: str | None = None
```

### Asset Path Generation
```python
def generate_asset_path(run_date: str, run_id: str, title: str) -> str:
    year = run_date[:4]
    slug = title_to_slug(title)
    run_id_suffix = run_id.split('-')[-1][:8]  # Last 8 chars of runId
    filename = f"{run_date}-{slug}-{run_id_suffix}.png"
    return f"public/gallery/{year}/{filename}"
```

## Main.py Expected Changes

### CLI Args
```python
parser.add_argument("--run-id", type=str, default=None,
                   help="Unique run identifier for idempotency (default: scheduled-{runDate})")
```

### Context Creation
```python
run_id = args.run_id or f"scheduled-{args.run_date}"
context = RunContext(
    run_date=args.run_date,
    run_id=run_id,
    ...
)
```

### Resolution Check
```python
pre_run = validate_pre_run_state(gallery, context.run_date, context.run_id)
if pre_run.existing_outcome:
    log_phase_complete("preflight", status=pre_run.existing_outcome)
    return 0  # Clean exit
```

## Bootstrap Changes (scripts/hosted-bootstrap.mjs)

### Scheduled Run ID Generation
```javascript
// For scheduled runs, use stable daily runId
const runId = process.env.HOSTED_RUN_ID || `scheduled-${runDateUTC}`;
const pythonArgs = [
  "-m", "orchestrator.main",
  "--repo-root", repoWorkspace,
  "--run-date", runDateUTC,
  "--run-id", runId,
  ...
];
```

## Hosted Smoke Proof Extension

Extend existing `hosted-smoke-checklist.md` to cover multi-run scenarios:

### Phase B-Extended: Durable Multi-Run Proof
1. First run: `hostedRunDateOverride=2099-04-01`, `hostedRunId=smoke-req-1`
   - Expected: One commit on `hosted-smoke` branch
2. Rerun same IDs: Same overrides
   - Expected: `already_resolved` log, 0 model calls, no second commit
3. Different run ID: `hostedRunId=smoke-req-2`, same date
   - Expected: Second commit on `hosted-smoke`, both images in gallery

### Phase C-Extended: Skip-Closes-Day Proof
1. Skip scenario: `hostedRunDateOverride=2099-04-02`, `hostedRunId=smoke-skip-1`, `fixture-scenario=skip-generation-failure`
   - Expected: One skip record for `2099-04-02`
2. Retry after skip: Same date, different `hostedRunId=smoke-skip-2`
   - Expected: `day_already_closed` log, 0 model calls, no publish

## Rejection Criteria

Butters will **reject** the implementation if any of these conditions are true:

1. **Duplicate gallery records:** Gallery contains duplicate (`runDate`, `runId`) pairs
2. **Skip-then-retry bypass:** Skip record exists, but manual retry proceeds with generation
3. **False collision:** Scheduled and manual runs same day incorrectly detect each other as duplicates
4. **Asset filename collision:** Two same-day runs write to same asset path
5. **Broken scheduled safety:** Scheduled retry creates second commit instead of no-op
6. **Frontend build failure:** `npm run build` fails after adding `runId` field
7. **Missing log correlation:** Phase logs missing `runId` field
8. **Deployed pipeline failure:** End-to-end hosted execution fails or generates no image
9. **Legacy image loss:** Existing pre-runId gallery images removed during or after new publish (BC-1 failure)
10. **Gallery overwrite:** New image replaces entire room.images[] instead of appending (BC-4 failure)

## Approval Criteria

Butters will **approve** closure of #16 when:

1. ✅ All 24 acceptance tests (SR-1 through BC-4) pass locally or hosted
2. ✅ `npm run orchestrator:proof` extended matrix passes (includes multi-run scenarios)
3. ✅ Frontend build remains green: `npm run build` exits 0
4. ✅ Hosted smoke proof (Phase B/C extended) passes on `hosted-smoke` branch
5. ✅ Deployed pipeline runs successfully and generates new gallery image
6. ✅ Log Analytics shows complete phase progression with `runId` correlation
7. ✅ No regression in existing scheduled run behavior
8. ✅ **Legacy preservation verified:** Existing pre-runId images remain in gallery after new publish (BC-1 gate)

## Close Gate Evidence Required

Per issue #16 acceptance criteria, before closing this issue provide:

1. **Deployed execution hash:** ACA Job execution name/ID from Azure portal
2. **Generated gallery record:** New image entry in `data/gallery.json` with `runId` field
3. **Asset proof:** New PNG in `public/gallery/{year}/` with `runId`-suffixed filename
4. **Commit hash:** Git SHA of the publish commit to `main`
5. **Log Analytics query:** KQL showing complete phase logs with `runId` correlation
6. **Validation logs:** Proof that same `runId` retry exits `already_resolved` with 0 calls

---

## References

- Issue: https://github.com/MaxBush6299/ArtofClawpilot/issues/16
- Skill: `.squad/skills/multi-run-validation-gates/SKILL.md`
- Prior gates: `docs/architecture/hosted-validation-gates.md`
- Smoke checklist: `docs/architecture/hosted-smoke-checklist.md`
- Team decisions: `.squad/decisions.md` (2026-04-27 multi-run section)
