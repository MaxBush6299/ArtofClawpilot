# Hosted validation and smoke gates

> Status: reviewer-start acceptance gates for issues #11 and #15.

This document gives Kyle a concrete validation target before the Python runtime lands. It is the tester-owned contract for daily-run correctness, dry-run coverage, and hosted smoke proof.

## Start-now call

- Kyle can start #7, #8, #9, and #11 now against these gates.
- Wendy should validate the frontend's `data/*.json` and `public/gallery/*` assumptions in parallel.
- Wendy's check is a cutover gate for #14/#15, not a blocker for backend implementation starting now.

## Non-negotiable release gates

1. **One outcome per UTC run date:** exactly one published image or exactly one structured skip record, never both.
2. **Bounded Artist budget:** one run attempt may use at most three `grok-4-20-reasoning` Artist calls and one `MAI-Image-2e` generation call.
3. **Reviewed prompt handoff:** image generation may consume only the final reviewed prompt package, not draft reasoning text.
4. **Reusable validation surface:** the same validation module must be callable from orchestrator execution, dry-run verification, and hosted smoke proof.
5. **Observable contract failures:** malformed reasoning output, missing reviewed prompt fields, and write-set invariant violations must produce explicit typed failures.

## Issue #6 pre-review gate

This is Butters's pre-implementation approval bar for **#6: end-to-end Python orchestrator for hosted execution**. It is a review checklist, not a verdict.

### Must-pass acceptance checks

Kyle does not clear #6 until review evidence shows all of the following:

1. **Single entrypoint:** one Python entrypoint resolves `runDate`, loads repo state, runs Curator/Critic/Artist in order, assembles exactly one typed outcome, validates it, and hands one write set to the hosted GitHub path.
2. **Idempotent preflight:** if `runDate` is already published or skipped, the orchestrator exits cleanly before any model call, asset write, or git mutation.
3. **Publish path:** a successful publish attempt yields one asset file, one image metadata entry in exactly one room, zero same-day skip records, and post-run validation success.
4. **Structured skip path:** controlled role/image failures yield one skip record, zero asset writes, zero same-day image entries, and post-run validation success.
5. **Explicit failure phases:** logs and exit handling identify where the run stopped (`pre_run`, `curator`, `critic`, `artist`, `publish`) and whether the result was publish, skip, no-op, or hard failure.
6. **Budget enforcement:** the orchestrator exposes final reasoning/image call counts and proves the Artist flow cannot exceed three reasoning calls or one image generation call for the same `runDate`.
7. **Reviewed prompt gate:** image generation consumes only the final reviewed package; draft/analyze payloads are never passed directly to `MAI-Image-2e`.

### Highest-risk gaps in the current repo

Current baseline risk areas to watch during review:

- `orchestrator/main.py` is still a preflight-only command; it does not yet execute roles, classify outcomes, persist a write set, or invoke the hosted GitHub write path.
- The repo has validation scaffolding, but no end-to-end dry-run or fixture-backed test surface today; `package.json` also still has no `npm test` command.
- The documented reviewed prompt contract requires final-ready fields such as reviewed prompt state and audit metadata, but the current Artist data model still centers on a generic prompt package and does not yet prove that draft output cannot leak into generation.
- Skip creation and typed phase failures exist as contracts, but there is not yet an integrated runtime path proving controlled failures become durable skips while auth/repo failures remain hard failures.
- Publish persistence is not wired yet: there is no current orchestrator module that writes the asset, updates `gallery.json`, and proves one-image-or-one-skip atomically for the target `runDate`.

### Evidence required for approval

To approve closure of #6, Butters will require:

- a code path review showing the real orchestrator entrypoint, role wiring, idempotency gate, outcome assembly, validation calls, and hosted write handoff
- deterministic run evidence for at least: publish happy path, structured skip path, already-resolved no-op path, and hard pre-run failure path
- logs or dry-run output that include resolved `runDate`, phase transitions, outcome kind, and final call counts
- proof that publish writes exactly one asset plus one image entry and that skip writes exactly one skip record with no asset
- proof that rerunning the same `runDate` performs zero model calls after the resolution check and creates no repo mutation
- confirmation that #15 can reuse the same orchestrator/validation surface without special-case test-only logic

## Validation categories

### 1. Pre-run validation

Pre-run validation must happen before any model call or git mutation.

| Check | Pass condition | Failure class |
| --- | --- | --- |
| `data/gallery.json` shape | valid JSON, `version`, `rooms[]`, optional `skipped[]`, unique room ids | hard fail |
| existing day resolution | `runDate` is absent from all room images and all skip records | clean no-op |
| gallery invariant | no existing `runDate` appears as both image and skip | hard fail |
| `data/critiques.json` shape | valid JSON with `entries[]` | hard fail |
| `data/next-brief.json` shape | valid JSON with expected brief fields | hard fail |
| runtime config | repo target, deployment names, API versions, and auth settings present | hard fail |

### 2. Role-output validation

Each role output is machine-checked immediately after parsing.

| Step | Required outcome | Failure handling |
| --- | --- | --- |
| Curator | target room id exists, artist brief is non-empty, style request is nullable but typed | structured skip at `curator` stage |
| Critic | if prior image exists, critique entry and suggestion are present and typed | structured skip at `critic` stage |
| Artist analyze | analysis payload is present and typed | structured skip at `artist` stage |
| Artist draft | draft prompt package is present and typed | structured skip at `artist` stage |
| Artist review | final reviewed prompt package is present and typed | structured skip at `artist` stage |

Malformed or partial `grok-4-20-reasoning` output is therefore a **domain contract failure**, not an infra failure, when repo/auth state is otherwise healthy.

### 3. Reviewed prompt package gate

The final Artist handoff is accepted only when all of the following are present:

- `reviewedPrompt`: final prompt text sent to `MAI-Image-2e`
- `promptSummary`: concise publishable summary for gallery metadata
- `artistNote`: human-readable note for the room page
- `reasoningAudit`: metadata proving the analyze, draft, and review steps completed in order
- `reviewStatus`: explicit final-ready marker rather than draft text

If any reviewed field is missing, empty, or still marked draft, image generation must not run.

### 4. Call-budget enforcement

The runtime must enforce these ceilings per run attempt:

| Call type | Maximum |
| --- | --- |
| Curator reasoning calls | 1 |
| Critic reasoning calls | 1 |
| Artist reasoning calls | 3 |
| Image generation calls | 1 |

Reviewer expectation:

- the Artist wrapper refuses a fourth reasoning call
- the image client refuses a second generation call for the same `runDate`
- logs or dry-run output expose the final call counts for assertion

Budget overflow is a structured skip at `artist` stage with an explicit reason such as `call_budget_exceeded`.

### 5. Post-run validation

| Outcome | Required durable effects | Rejection conditions |
| --- | --- | --- |
| publish | one new file under `public/gallery/`, one new image entry for exactly one room, zero new skip records for the same `runDate` | multiple assets, multiple image entries, any same-day skip, bad path, missing metadata |
| skip | zero new gallery asset files, one new skip record for `runDate`, zero new image entries for the same `runDate` | any new asset, any same-day image entry, missing skip fields |
| idempotent rerun | zero model calls after pre-run resolution check, zero repo mutation | any write or extra model call |

Required published image metadata remains:

- `id`
- `title`
- `path`
- `createdAt`
- `promptSummary`
- `artistNote`
- `runDate`
- `model`
- optional `criticism`
- optional `reasoningModel`

Required skip metadata remains:

- `id`
- `runDate`
- `stage`
- `reasonCode`
- `message`
- `createdAt`
- `retryable`
- `error.code`
- `error.message`
- `creativeContext` when the run reached reviewed-prompt or image-generation handling

## Minimum dry-run coverage for #15

Kyle's dry-run path should exercise the real orchestrator and validation layer without pushing to `main` or mutating production gallery state.

Minimum scenarios:

| Scenario | Expected result |
| --- | --- |
| publish happy path | publish write set validates and exits success without production push |
| image generation failure | structured skip write set validates |
| malformed Curator output | explicit contract failure becomes structured skip |
| malformed Critic output | explicit contract failure becomes structured skip |
| malformed Artist reviewed package | image generation is blocked and a structured skip is produced |
| Artist call-budget overflow attempt | fourth reasoning call is refused and surfaced as contract failure |
| already-resolved run date | clean no-op with zero new model calls after resolution check |
| corrupted pre-run JSON/config | hard fail before any model call |

Dry-run acceptance is not met unless those scenarios can be rerun repeatably from fixtures or deterministic stubs.

### Repeatable proof command

Issue #15's deterministic local proof command is:

```text
npm run orchestrator:proof
```

That command clones the repo into disposable `workspace/issue-15-proof/*` checkouts, seeds prior gallery state when the Critic path must run, executes `python -m orchestrator.main --dry-run --allow-dirty --use-fixtures`, and asserts each dry run leaves the seeded checkout diff unchanged. The proof matrix now covers publish, structured generation-failure skip, malformed Curator/Critic/Artist output, Artist call-budget overflow, same-day no-op, and corrupted pre-run JSON.

## Minimum hosted smoke proof

Before enabling the Azure scheduler as the primary runtime, Butters expects the manual-first ACA Job procedure in [`hosted-smoke-checklist.md`](./hosted-smoke-checklist.md) to pass. The minimum hosted proof is now split on purpose:

1. **Phase A:** manual dry-run auth/wiring probe on the real ACA Job with managed identity, Key Vault references, GitHub App auth, and fixture-backed orchestrator startup.
2. **Phase B:** manual durable publish proof on a disposable `hosted-smoke` branch with `hostedPushChanges=true`, one publish commit, and a same-`runDate` rerun that exits `already_resolved` with no second commit.
3. **Phase C:** manual durable failure-path proof on the same smoke branch showing one hosted failure fixture becomes the expected structured skip outcome.
4. Wendy confirms the frontend still tolerates `skipped[]` plus optional audit fields.

The manual hosted procedure remains documented in [`hosted-smoke-checklist.md`](./hosted-smoke-checklist.md). Engineers should treat the local proof matrix above as the precondition for every hosted smoke attempt.

## Promotion bar

Butters should reject cutover unless all of the following are true:

- #11 lands one reusable validation module shared by orchestrator, dry-run, and hosted smoke.
- #15 demonstrates every scenario in the dry-run coverage table.
- Hosted smoke passes on real container/job wiring by following `hosted-smoke-checklist.md`.
- Wendy signs off that the frontend tolerates `gallery.json` contract growth.
- One-image-or-one-skip remains provable for every tested `runDate`.
