# BC-1 Legacy Preservation Gate for Issue #16

**Author:** Butters  
**Date:** 2026-04-27  
**Context:** Issue #16 reopened regression

## Decision

Issue #16 deployed refactor must preserve all existing gallery images when adding new images. The current implementation overwrote "Primordial Coalescence" (commit a57c085) with "Inaugural Hall: Dawn of Creation" (commit e5c07c5) despite both PNG assets existing on disk.

## Rationale

Gallery preservation is a core invariant: deployed runs must append to the gallery, never replace existing content. The pre-deployment validation matrix lacked backward compatibility tests for legacy pre-runId images coexisting with new runId-based images.

## New Acceptance Gates

### BC-1: Legacy Image Preservation (Critical)
- **Given:** Gallery contains one or more pre-runId images (has `runDate`, no `runId` field)
- **When:** New orchestrator run publishes with `runId=scheduled-{date}`
- **Then:** Gallery must contain ALL legacy images PLUS the new image
- **Rejection if:** Any existing image removed from gallery.json

### BC-2: Effective Run ID Fallback
- Pre-runId images return `id` value from `effective_run_id()` method
- Never returns None or crashes

### BC-3: Mixed Gallery Frontend Tolerance
- Home.tsx and Room.tsx render both legacy (no runId) and new (with runId) images without crashes

### BC-4: Gallery Array Append Behavior
- New images appended to `room.images[]` array
- Existing images not replaced or filtered out

## Evidence

```bash
# Both assets exist on disk:
public/gallery/2026/2026-04-27-primordial-coalescence.png (1.54MB)
public/gallery/2026/2026-04-27-inaugural-hall-dawn-of-creation-27.png (1.39MB)

# But gallery.json contained only the newer image
git diff a57c085 e5c07c5 -- data/gallery.json
# Shows "Primordial Coalescence" replaced with "Inaugural Hall: Dawn of Creation"
```

## Recommended Fix Path

1. **Root cause analysis:** Investigate orchestrator gallery persistence logic to identify where `room.images[]` is replaced instead of appended
2. **Code fix:** Update persistence to preserve existing images when adding new ones
3. **BC-1 proof:** Create test scenario with seeded legacy image, run orchestrator, verify both images present
4. **Validation:** Run extended orchestrator proof matrix including BC-1 through BC-4
5. **Deployment gate:** Verify legacy preservation on smoke branch before production

## Acceptance Criteria Before Re-Closure

- [ ] All 24 tests (SR-1 through BC-4) pass
- [ ] BC-1 proof scenario added to orchestrator proof script
- [ ] Extended validation checklist committed with BC gates
- [ ] Deployed smoke run preserves seeded legacy image
- [ ] Log Analytics shows no "image_overwrite" or similar warnings
- [ ] Manual verification: both "Primordial Coalescence" and "Inaugural Hall" visible in production gallery

## Severity

**BLOCKER** - Production gallery data loss violates core preservation invariant. Issue #16 must remain OPEN until BC-1 gate passes.

## Reviewer Lockout Note

Per team policy, Kyle is locked out from fixing this regression due to prior rejection on 6e82793. Assign to Stan, Tolkien, or available engineer.

## References

- Commit 468013c: BC-1 gate definition
- Issue #16: https://github.com/MaxBush6299/ArtofClawpilot/issues/16
- Validation checklist: `docs/workspace/issue-16-validation-checklist.md`
- Proof plan: `docs/workspace/issue-16-proof-extension-plan.md`
- Deploy gate: `docs/architecture/issue-16-deploy-gate.md`
- Skill: `.squad/skills/gallery-preservation-validation/SKILL.md`
