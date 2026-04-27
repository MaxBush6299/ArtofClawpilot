# Hosted smoke checklist

> Status: issue #15 cutover-proof procedure for the Azure Container Apps Job path.

This checklist makes the hosted smoke bar concrete without turning the scheduler on too early. It uses the existing ACA Job, user-assigned managed identity, Key Vault references, GitHub App write path, and Log Analytics diagnostics already in this repo.

## Safety stance

Deploy the hosted runner in a **manual-first** profile until the smoke proof passes:

- `jobTriggerType=Manual`
- `hostedPushChanges=false` for the first auth/wiring probe
- `githubBranch=hosted-smoke` for any durable commit proof
- `hostedRunDateOverride=<fixed UTC date>` whenever you need repeatable reruns

Do **not** promote to `jobTriggerType=Schedule` on `main` until Butters signs off on the evidence below.

## Required deployment knobs

`infra/main.bicep` now exposes the minimum platform surface needed for safe smoke verification:

| Parameter | Smoke use |
| --- | --- |
| `jobTriggerType` | Keep the ACA Job manual until cutover. |
| `githubBranch` | Point durable smoke commits at `hosted-smoke`, not `main`. |
| `hostedPushChanges` | Keep `false` for auth-only probes; set `true` only for disposable smoke-branch proof. |
| `hostedRunnerCommand` | Switch between publish and failure fixtures without rebuilding the image. |
| `hostedRunDateOverride` | Replay the same logical day to prove idempotent no-op behavior. |

## Evidence sources

- ACA Job execution history for the execution name
- `ContainerAppConsoleLogs_CL` for bootstrap + orchestrator JSON logs
- Git history on the smoke branch when durable proof is enabled

Representative KQL:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerGroupName_s startswith "<job-execution-name>"
| project TimeGenerated, ContainerName_s, Log_s
| order by TimeGenerated asc
```

## Phase A — wiring and auth probe

Purpose: prove the real container, managed identity, Key Vault references, GitHub App auth, and orchestrator startup all work **without** writing a commit.

### Deploy/profile

- `jobTriggerType=Manual`
- `hostedPushChanges=false`
- `githubBranch=main`
- `hostedRunDateOverride=2099-02-10`
- `hostedRunnerCommand=python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --dry-run --use-fixtures --fixture-scenario publish`

### Execute

1. Start the ACA Job manually.
2. Capture the execution name from the Azure portal or `az containerapp job execution list`.
3. Query the console logs for that execution.

### Must-see evidence

- bootstrap `run_started`
- bootstrap `token_acquired`
- orchestrator `run_started`
- orchestrator `preflight_validated`
- orchestrator `dry_run_validated`
- final call-count proof in the same execution log stream

### Failure interpretation

- Missing `token_acquired` means the GitHub App or Key Vault path is still broken.
- Missing orchestrator `run_started` after bootstrap success means the container command or Python path is broken.
- Any hard failure here blocks Phase B.

## Phase B — durable publish and idempotent rerun proof

Purpose: prove the real hosted path can create one durable outcome and then cleanly no-op on the same `runId`.

### Deploy/profile

- `jobTriggerType=Manual`
- `githubBranch=hosted-smoke`
- `hostedPushChanges=true`
- `hostedRunDateOverride=2099-02-11`
- `hostedRunnerCommand=python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --use-fixtures --fixture-scenario publish`

### Execute

1. Start the job manually once.
2. Confirm the smoke branch receives exactly one commit for `2099-02-11`.
3. Start the same job again with the same `hostedRunDateOverride` and `runId` value (using the same fixtures so the `runId` is stable).

### Must-see evidence

First execution:

- orchestrator `write_set_validated`
- orchestrator `commit_ready`
- bootstrap `push_completed`
- one commit on `hosted-smoke`

Second execution:

- orchestrator `already_resolved`
- final call counts show no additional model/image calls after resolution
- no second smoke commit for `2099-02-11` with same `runId`

## Phase C — durable failure-path proof

Purpose: prove hosted failure classification matches the local dry-run contract.

### Deploy/profile

- keep `jobTriggerType=Manual`
- keep `githubBranch=hosted-smoke`
- keep `hostedPushChanges=true`
- change `hostedRunDateOverride=2099-02-12`
- change `hostedRunnerCommand=python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --use-fixtures --fixture-scenario skip-generation-failure`

### Execute

1. Start the job manually once.
2. Review the smoke-branch commit and ACA logs.

### Must-see evidence

- orchestrator `skip_outcome_validated`
- orchestrator `write_set_validated`
- bootstrap `push_completed`
- smoke branch contains one skip outcome for `2099-02-12`
- no gallery asset was added for that date

## Promotion bar

Do not switch hosted execution to the scheduler on `main` until all of the following are true:

1. The local dry-run matrix from `docs/architecture/hosted-validation-gates.md` has been completed.
2. Phase A proves managed identity, Key Vault, GitHub App auth, container command, and orchestrator startup on the real ACA Job.
3. Phase B proves one durable publish on the smoke branch and a same-`runId` idempotent rerun no-op.
4. Phase C proves one hosted failure path becomes the expected structured skip contract.
5. Wendy signs off that frontend reads still tolerate `skipped[]` plus optional audit fields.
6. Butters signs off on the collected dry-run + hosted evidence.

## Promotion profile

After sign-off, redeploy the job with the production profile:

- `jobTriggerType=Schedule`
- `githubBranch=main`
- `hostedPushChanges=true`
- clear `hostedRunDateOverride`
- restore the default `hostedRunnerCommand` without fixtures or `--dry-run`

That redeploy is the cutover point from manual proof to scheduled hosted runtime.
