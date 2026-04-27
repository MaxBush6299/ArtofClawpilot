# Issue #16 Deployed Pipeline Close Gate

> **Issue:** [#16](https://github.com/MaxBush6299/ArtofClawpilot/issues/16) — Refactor hosted run identity to support multiple same-day artworks  
> **Status:** Implementation pending. This document defines the deployed validation gate that must pass before the issue can close.

## Close Gate Requirement

Before issue #16 can close, the team must run the deployed hosted pipeline end to end successfully and generate another image in the gallery using the refactored run identity contract.

**Gate criteria:**
1. Kyle's run identity implementation is complete and reviewed
2. Deployed ACA Job executes with the new `runId` contract
3. At least one successful image generation with distinct `runId`
4. Evidence captured: execution logs, commit SHA, gallery record, validation proof

---

## Azure Container Apps Job Settings Required

### Environment Variables to Add/Update

The following environment variables must be added or updated in the ACA Job configuration to support distinct run identities:

#### New Required Variables

| Variable | Purpose | Example Value | Source |
|----------|---------|---------------|--------|
| `RUN_ID` | Unique run identifier for idempotency | `scheduled-2026-04-28` or `manual-2026-04-28-abc123` | Job execution input |
| `TRIGGER_SOURCE` | Identifies how the run was initiated | `scheduled`, `manual-api`, `manual-cli` | Job execution metadata |

#### Existing Variables to Preserve

| Variable | Current Purpose | Notes |
|----------|-----------------|-------|
| `RUN_DATE_UTC` | UTC calendar date | Remains as grouping field, not idempotency key |
| `HOSTED_TRACE_ID` | Log correlation ID | May be replaced or supplemented by `RUN_ID` |

### Bicep Parameter Updates

Add these parameters to `infra/main.bicep`:

```bicep
@description('Optional run identifier for manual execution. Scheduled runs use runId=scheduled-{runDate}.')
param hostedRunId string = ''

@description('Trigger source for this execution: scheduled, manual-api, or manual-cli.')
@allowed([
  'scheduled'
  'manual-api'
  'manual-cli'
])
param hostedTriggerSource string = 'scheduled'
```

### Job Template Environment Update

Update the job template in `infra/main.bicep` to inject the new variables:

```bicep
{
  name: 'RUN_ID'
  value: !empty(hostedRunId) ? hostedRunId : 'scheduled-${runDate}'
}
{
  name: 'TRIGGER_SOURCE'
  value: hostedTriggerSource
}
```

---

## Hosted Bootstrap Changes

`scripts/hosted-bootstrap.mjs` will need to pass `RUN_ID` and `TRIGGER_SOURCE` to the orchestrator:

### Updated Environment Injection

```javascript
env: {
  ...process.env,
  REPO_WORKSPACE: clonePath,
  RUN_DATE_UTC: runDate,
  RUN_ID: process.env.RUN_ID || `scheduled-${runDate}`,
  TRIGGER_SOURCE: process.env.TRIGGER_SOURCE || 'scheduled',
  HOSTED_TRACE_ID: traceId,
}
```

### Updated Log Context

```javascript
setLogContext({
  runDate,
  runId: process.env.RUN_ID || `scheduled-${runDate}`,
  triggerSource: process.env.TRIGGER_SOURCE || 'scheduled',
  traceId,
});
```

---

## Orchestrator CLI Updates

The orchestrator must accept `--run-id` and `--trigger-source` arguments:

### Expected Command Shape

**Scheduled runs:**
```bash
python3 -m orchestrator.main \
  --repo-root "$REPO_WORKSPACE" \
  --run-date "$RUN_DATE_UTC" \
  --run-id "$RUN_ID" \
  --trigger-source "$TRIGGER_SOURCE"
```

**Manual smoke proof:**
```bash
python3 -m orchestrator.main \
  --repo-root "$REPO_WORKSPACE" \
  --run-date "2099-02-15" \
  --run-id "manual-2099-02-15-smoke" \
  --trigger-source "manual-cli" \
  --use-fixtures \
  --fixture-scenario publish
```

---

## Evidence to Capture

### 1. Pre-Deployment Checklist

Before executing the deployed validation:

- [ ] Kyle's implementation PR merged to main
- [ ] Butters reviewed and approved the run identity contract
- [ ] Bicep parameters updated with `hostedRunId` and `hostedTriggerSource`
- [ ] Infrastructure redeployed with updated parameters
- [ ] Hosted bootstrap updated to inject new environment variables
- [ ] Orchestrator CLI accepts `--run-id` and `--trigger-source`

### 2. Execution Evidence

Capture the following for each validation run:

#### Log Analytics Query

```kusto
ContainerAppConsoleLogs_CL
| where ContainerGroupName_s startswith "<execution-name>"
| where Log_s contains "runId" or Log_s contains "triggerSource"
| project TimeGenerated, ContainerName_s, Log_s
| order by TimeGenerated asc
```

**Must show:**
- Bootstrap `run_started` event with `runId` and `triggerSource` fields
- Orchestrator `run_started` with matching `runId`
- Idempotency check references `runId` (not just `runDate`)
- Validation logs include `runId` in all phases

#### Git Commit Evidence

```bash
# Latest commit on target branch
gh api repos/MaxBush6299/ArtofClawpilot/commits/main --jq '.sha, .commit.message'

# Verify gallery.json contains runId field
gh api repos/MaxBush6299/ArtofClawpilot/contents/data/gallery.json \
  --jq '.content' | base64 -d | jq '.rooms[].images[-1].runId'
```

**Must show:**
- Commit SHA and message include run date reference
- Gallery record contains `runId` field with expected value
- Asset path includes safe identifier (no collision risk)

#### Gallery Record Structure

```json
{
  "id": "2026-04-28-example-title",
  "runId": "scheduled-2026-04-28",
  "triggerSource": "scheduled",
  "runDate": "2026-04-28",
  "title": "Example Title",
  "path": "public/gallery/2026/2026-04-28-example-title.png",
  "createdAt": "2026-04-28T07:00:00Z",
  "promptSummary": "...",
  "artistNote": "...",
  "model": "MAI-Image-2e"
}
```

### 3. Multi-Run Validation (Optional for Close Gate)

If Kyle's implementation includes multi-run support, validate with two same-day executions:

**First run:**
```bash
az containerapp job start \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --args "--run-date 2099-02-16 --run-id manual-2099-02-16-test1 --trigger-source manual-cli"
```

**Second run (same day, different runId):**
```bash
az containerapp job start \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --args "--run-date 2099-02-16 --run-id manual-2099-02-16-test2 --trigger-source manual-cli"
```

**Must show:**
- Both executions complete successfully
- Two distinct gallery records with same `runDate`, different `runId`
- No asset path collisions
- No git push conflicts

---

## Safe Command Plan for Validation

### Phase 0: Pre-Flight Check

```bash
# Verify current deployment state
az containerapp job show \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --query "{name:name,triggerType:properties.configuration.triggerType,image:properties.template.containers[0].image}"

# Verify Key Vault secrets are accessible
az keyvault secret list \
  --vault-name <kv-name> \
  --query "[].{name:name,enabled:attributes.enabled}" -o table
```

### Phase 1: Infrastructure Update

**DO NOT RUN UNTIL KYLE'S IMPLEMENTATION IS COMPLETE**

```bash
# Redeploy with updated parameters
az deployment group create \
  --resource-group rg-evaldemo \
  --template-file infra/main.bicep \
  --parameters infra/main.json \
  --parameters hostedRunId='scheduled-2026-04-28' \
  --parameters hostedTriggerSource='scheduled' \
  --parameters jobTriggerType='Manual'
```

### Phase 2: Smoke Execution with Fixtures

```bash
# Start manual job with fixture scenario
az containerapp job start \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --env-vars \
    HOSTED_RUNNER_COMMAND='python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --run-id "$RUN_ID" --trigger-source "$TRIGGER_SOURCE" --use-fixtures --fixture-scenario publish' \
    RUN_DATE_UTC='2099-02-17' \
    RUN_ID='manual-2099-02-17-smoke' \
    TRIGGER_SOURCE='manual-cli' \
    HOSTED_PUSH_CHANGES='true' \
    GITHUB_BRANCH='hosted-smoke'

# Capture execution name from output
EXECUTION_NAME=<from-output>

# Wait 2 minutes, then check logs
az containerapp job execution logs show \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --execution-name $EXECUTION_NAME
```

### Phase 3: Production Validation

**ONLY RUN AFTER PHASE 2 PASSES**

```bash
# Execute against main with real orchestrator
az containerapp job start \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --env-vars \
    RUN_DATE_UTC='<today-or-future-date>' \
    RUN_ID='scheduled-<date>' \
    TRIGGER_SOURCE='scheduled' \
    HOSTED_PUSH_CHANGES='true' \
    GITHUB_BRANCH='main'

# Capture execution and verify
EXECUTION_NAME=<from-output>
az containerapp job execution show \
  --name artclaw-daily-job-2pewehrfleuls \
  --resource-group rg-evaldemo \
  --execution-name $EXECUTION_NAME \
  --query "{status:properties.status,startTime:properties.startTime,endTime:properties.endTime}"
```

### Phase 4: Evidence Collection

```bash
# Query Log Analytics (replace workspace ID and execution name)
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerGroupName_s startswith '<execution-name>' | project TimeGenerated, Log_s | order by TimeGenerated asc" \
  --output table

# Verify git commit
gh api repos/MaxBush6299/ArtofClawpilot/commits/main \
  --jq '{sha:.sha, message:.commit.message, date:.commit.author.date}'

# Verify gallery record
gh api repos/MaxBush6299/ArtofClawpilot/contents/data/gallery.json \
  --jq '.content' | base64 -d | jq '.rooms[].images | map(select(.runId != null))'
```

---

## Success Criteria for Close Gate

### Must Pass

- [ ] Kyle's run identity implementation merged and reviewed
- [ ] Infrastructure redeployed with `runId` and `triggerSource` support
- [ ] Bootstrap passes new variables to orchestrator
- [ ] Orchestrator accepts and uses `--run-id` and `--trigger-source`
- [ ] At least one successful deployed execution generates an image
- [ ] Log Analytics shows `runId` in all structured logs
- [ ] Gallery record contains `runId` and `triggerSource` fields
- [ ] Idempotent rerun with same `runId` exits as `already_resolved`
- [ ] Commit lands on main (or smoke branch for pre-production validation)

### Optional (Nice to Have)

- [ ] Two same-day manual runs with distinct `runId` both succeed
- [ ] Asset paths do not collide for same-day runs
- [ ] Frontend displays multiple same-day images correctly

---

## Rollback Plan

If validation fails and blocks promotion:

1. **Preserve evidence:** Save execution logs, error messages, and any partial commits
2. **Do not retry on main:** Use smoke branch for debugging
3. **Revert infrastructure if needed:**
   ```bash
   az deployment group create \
     --resource-group rg-evaldemo \
     --template-file infra/main.bicep \
     --parameters infra/main.json \
     --parameters jobTriggerType='Manual'
   ```
4. **Document failure in issue #16:** Include logs, error classification, and recommended fix
5. **Return to Kyle for iteration**

---

## Related Documentation

- [Issue #16](https://github.com/MaxBush6299/ArtofClawpilot/issues/16) — Run identity refactor
- [docs/architecture/hosted-smoke-checklist.md](./hosted-smoke-checklist.md) — Smoke testing procedure
- [docs/architecture/hosted-daily-run.md](./hosted-daily-run.md) — Hosted execution contract
- [.squad/skills/manual-aca-job-smoke-gate/SKILL.md](../../.squad/skills/manual-aca-job-smoke-gate/SKILL.md) — Smoke gate pattern

---

## Change History

- 2026-04-27: Initial draft by Tolkien for issue #16 close gate
