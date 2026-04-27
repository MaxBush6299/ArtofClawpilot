---
name: "gallery-preservation-validation"
description: "Validation pattern for ensuring gallery ledger preservation during schema evolution and multi-run refactors."
domain: "testing"
confidence: "high"
source: "earned"
tools:
  - name: "git"
    description: "Tracks gallery.json diffs and validates append-only semantics."
    when: "Reviewing commits for gallery preservation violations."
  - name: "powershell"
    description: "Verifies asset file existence matches gallery.json records."
    when: "Validating no orphaned records or missing assets after refactor."
---

## Context

Use this pattern when the gallery schema evolves (e.g., adding `runId` field) or multi-run support is deployed. Gallery preservation is a core invariant: deployed runs must append to the gallery ledger, never replace or delete existing content. This pattern applies when:

- Adding optional fields to `GalleryImageRecord` (e.g., `runId`, `triggerSource`)
- Refactoring idempotency checks from single-key to composite-key
- Deploying backward-compatible schema changes
- Validating hosted execution against production gallery state

## Patterns

### Gallery Ledger Preservation Invariant

**Core Rule:** Every gallery commit must preserve all existing images and skip records. New images append to `room.images[]` array; existing records remain unchanged.

**Anti-pattern:** Replacing `room.images[]` array instead of appending new entries.

### Backward Compatibility Gate (BC-1)

Before deploying schema changes, validate that:

1. **Legacy records coexist with new records:** Pre-refactor images (lacking new optional fields) remain in gallery after new images publish
2. **Effective identity resolution:** Code handling optional fields uses safe fallback (e.g., `self.run_id or self.id`)
3. **Mixed gallery rendering:** Frontend displays both legacy and new records without crashes
4. **Array append semantics:** New images added to end of `room.images[]`, not replacing array

### Evidence-Based Validation

Validate preservation using concrete evidence:

```bash
# Check both assets exist on disk
ls public/gallery/2026/*.png

# Verify gallery.json contains both records
jq '.rooms[].images | length' data/gallery.json

# Compare commits to detect overwrites
git diff <before-commit> <after-commit> -- data/gallery.json
```

### Proof Scenario Pattern

```python
# Seed gallery with legacy image (missing new optional field)
def seed_legacy_image(scenario_root: Path) -> None:
    legacy_gallery = {
        "version": 1,
        "rooms": [{
            "id": "room-01",
            "images": [{
                "id": "2026-04-27",
                "title": "Legacy Image",
                "runDate": "2026-04-27",
                # Missing: runId field
            }]
        }]
    }
    write_gallery(scenario_root, legacy_gallery)

# Run orchestrator with new schema
# Validate: both legacy and new images present
def validate_preservation(summary: dict) -> None:
    gallery = load_gallery()
    images = gallery.rooms[0].images
    assert len(images) >= 2  # Legacy + new
    
    # Find legacy image (no runId)
    legacy = [img for img in images if img.run_id is None]
    assert len(legacy) >= 1  # Not removed
    
    # Find new image (has runId)
    new = [img for img in images if img.run_id is not None]
    assert len(new) >= 1  # Successfully added
```

## Examples

### Example 1: Issue #16 Regression

**Scenario:** Deployed runId refactor overwrote "Primordial Coalescence" with "Inaugural Hall: Dawn of Creation" in gallery.json.

**Evidence:**
- Both PNG assets present: `2026-04-27-primordial-coalescence.png` (1.54MB), `2026-04-27-inaugural-hall-dawn-of-creation-27.png` (1.39MB)
- Git diff shows gallery.json replaced instead of appended
- Commit a57c085 → e5c07c5

**Root Cause:** Gallery persistence logic replaced `room.images[]` array instead of appending new entry.

**Fix:** Update persistence to preserve existing images when adding new ones.

### Example 2: BC-1 Acceptance Test

```python
Scenario(
    "legacy-image-preservation",
    "publish",
    seed_legacy_image_then_new_publish,
    0,
    validate_legacy_preserved
)
```

**Setup:** Seed gallery with pre-runId image (has `runDate`, no `runId` field)

**Execute:** Run orchestrator with `--run-id scheduled-2026-04-28`

**Validate:** Gallery contains BOTH legacy image AND new image

### Example 3: Asset-Record Consistency Check

```bash
# List all PNG assets
ls public/gallery/*/*.png | wc -l

# Count gallery.json image records
jq '[.rooms[].images[]] | length' data/gallery.json

# Both counts must match (no orphaned records or missing assets)
```

## Anti-Patterns

- **Deploy schema changes without BC-1 gate:** Pre-deployment validation MUST include legacy image preservation proof.
- **Replace arrays instead of append:** Always append to `room.images[]`, never reassign the array.
- **Ignore asset-record drift:** After every deployment, verify PNG count matches gallery.json image count.
- **Skip mixed-gallery frontend validation:** Test that Home.tsx and Room.tsx render both legacy and new records without crashes.
- **Assume backward compatibility works:** Explicitly test that optional fields default correctly for legacy records.

## Validation Checklist

Before deploying gallery schema changes:

- [ ] BC-1 proof scenario added to orchestrator proof script
- [ ] Legacy image seeded, new image published, both present in gallery
- [ ] Effective identity resolution uses safe fallback (e.g., `run_id or id`)
- [ ] Frontend build passes with mixed gallery (legacy + new)
- [ ] Asset file count matches gallery.json image record count
- [ ] Git diff shows append-only changes (no deletions or replacements)
- [ ] Deployed smoke run preserves seeded legacy image
- [ ] Log Analytics shows no "overwrite" or "replace" warnings

## References

- Issue #16 reopened regression (commits a57c085 → e5c07c5)
- `docs/workspace/issue-16-validation-checklist.md` (BC-1 through BC-4 gates)
- `docs/workspace/issue-16-proof-extension-plan.md` (seed_legacy_image_then_new_publish scenario)
- `docs/architecture/issue-16-deploy-gate.md` (legacy preservation checkpoints)
- `.squad/agents/butters/history.md` (2026-04-27 BC-1 gate learnings)
