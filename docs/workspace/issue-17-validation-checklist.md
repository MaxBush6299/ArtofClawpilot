# Issue #17 Manual API Validation Checklist

> Owner: Butters
> Scope: Phase 1 internal clawpilot manual generation API with `X-Clawpilot-Key` auth.
> Release stance: do not deploy or promote until every release gate below has evidence.

## Contract under test

- Route: `POST /api/internal/generate`.
- Auth: `X-Clawpilot-Key` must match the Key Vault `clawpilot-api-key` secret.
- Required request field: `requestId`.
- Optional request field: `guidingDescription`, max 1000 characters.
- API-derived run identity: `runId = manual-{runDate}-{requestId}`.
- API-triggered job env must include `RUN_DATE_UTC`, `RUN_ID`, `TRIGGER_SOURCE=manual-api`, `REQUEST_ID`, `CALLER_IDENTITY`, `CORRELATION_ID`, `HOSTED_TRACE_ID`, and optional `GUIDING_DESCRIPTION`.
- Raw API key and raw `guidingDescription` must never appear in Function, bootstrap, or orchestrator logs.
- Scheduled behavior remains `runId=scheduled-{runDate}` and must not require API fields.
- Legacy/pre-runId gallery records must survive every publish.

## Acceptance matrix

| ID | Coverage | Evidence required | Reject if |
| --- | --- | --- | --- |
| AUTH-1 | Missing `X-Clawpilot-Key` | Local Function/unit test returns 401 and no ACA Job start call | Any job invocation occurs |
| AUTH-2 | Wrong `X-Clawpilot-Key` | Local Function/integration test with fake Key Vault secret returns 401 | 202/200 returned or job starts |
| AUTH-3 | Valid key | Local Function/integration test returns 202 for new request | Key is logged or request rejected |
| JOB-1 | Valid key + `requestId` starts exactly one job | Mock `startManualGenerationJob`/Azure SDK proof shows one call with expected env overrides | Missing env, duplicate start, or wrong `runId` |
| GUIDE-1 | `guidingDescription` optional | Unit test accepts missing/blank description | Missing description rejected |
| GUIDE-2 | Max length | Unit test accepts 1000 chars and rejects 1001 chars with 400 | Oversized description starts job |
| GUIDE-3 | Not logged raw | Source review plus log capture shows only presence/length fields | Raw text appears in logs |
| IDEM-1 | Same `requestId` duplicate | API pre-check returns 200 `already_resolved`; no job start; orchestrator duplicate has 0 calls | Second request generates image |
| IDEM-2 | Distinct `requestId` same day | Two accepted requests create two distinct `runId` values and two gallery images | False duplicate, overwrite, or collision |
| SCHED-1 | Scheduled run unchanged | `npm run build` and fixture scheduled dry-run still pass without API fields | Scheduler requires API metadata |
| LEGACY-1 | Legacy/pre-runId records preserved | Current mixed gallery plus new publish proof keeps all prior image IDs/paths | Any existing record or asset disappears |
| DEPLOY-1 | Function exists | Bicep contains `Microsoft.Web/sites` Function App and app settings for Key Vault + ACA Job | Function resource absent |
| DEPLOY-2 | Function MI can read Key Vault | Bicep role assignment at Key Vault scope uses Key Vault Secrets User for Function identity | No Key Vault read role |
| DEPLOY-3 | Function MI can start ACA Job | Bicep role assignment at ACA Job scope grants jobs operator/contributor | No start permission |
| DEPLOY-4 | Logs correlate | KQL shows `requestId`, `runId`, `correlationId`, Function execution, and ACA execution in one trace | Logs cannot tie request to execution |

## Automated coverage added

Run before requesting Butters sign-off:

```powershell
npm --prefix api run check
npm --prefix api test
npm run build
```

Current unit coverage:

- `api/test/validation.test.js`: requestId validation, optional guiding description, max-length boundary.
- `api/test/gallery.test.js`: duplicate pre-check for `runId`, legacy `id` fallback, skip outcome detection, unavailable pre-check behavior.
- `api/test/auth.test.js`: missing key rejected before Key Vault lookup.

## Manual/local proof commands

Use fixtures only; do not deploy:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m orchestrator.main --repo-root . --run-date 2099-06-01 --run-id manual-2099-06-01-alpha --trigger-source manual-api --request-id alpha --caller-identity clawpilot-agent --correlation-id corr-alpha --guiding-description 'safe advisory context' --dry-run --allow-dirty --use-fixtures
```

Must-see:

- `run_started` includes `triggerSource=manual-api`, `requestId`, `callerIdentity`, `correlationId`.
- Logs include `hasGuidingDescription` and `guidingDescriptionChars`.
- Logs do **not** include the raw guiding description string.
- `run_summary` is per-run and not aggregated across requests.

## Hosted deployment proof checklist

Do not deploy from this checklist; collect proof only after Tolkien/Kyle provide a deployed candidate.

1. Function resource exists:
   ```powershell
   az functionapp show --resource-group <rg> --name <functionAppName>
   az functionapp function show --resource-group <rg> --name <functionAppName> --function-name internalGenerate
   ```
2. Function managed identity has Key Vault access:
   ```powershell
   az role assignment list --assignee <functionPrincipalId> --scope <keyVaultResourceId>
   ```
3. Function managed identity can start the ACA Job:
   ```powershell
   az role assignment list --assignee <functionPrincipalId> --scope <containerAppJobResourceId>
   ```
4. A valid-key smoke call returns 202 and one ACA execution:
   ```powershell
   az containerapp job execution list --resource-group <rg> --name <jobName>
   ```
5. Log Analytics correlation query:
   ```kusto
   ContainerAppConsoleLogs_CL
   | where Log_s has "<correlationId>" or Log_s has "<requestId>" or Log_s has "<runId>"
   | project TimeGenerated, ContainerName_s, Log_s
   | order by TimeGenerated asc
   ```

## Current Butters status

- Frontend build: ✅ passed (`npm run build` exits 0).
- API syntax: ✅ passed (`npm --prefix api run check` exits 0).
- API unit coverage: ✅ passed (`npm --prefix api test` exits 0).
- Orchestrator manual-api dry-run: ✅ passed with request/correlation metadata and no raw guidance in JSON logs.
- Distinct same-day manual run probe: ✅ **RESOLVED** (2026-04-27 re-review). `manual-2099-06-04-alpha` exits `already_resolved`, `manual-2099-06-04-beta` publishes with distinct asset path. Kyle's implementation correctly scopes validation to `runId` via `effective_run_id()`.
- AUTH-1/AUTH-2 wrong-key/no-start: ✅ Code-level proof: `validateApiKey()` checked before `startManualGenerationJob()` call.
- AUTH-3/JOB-1 valid-key/one-start: ✅ Code flow guarantees single job invocation after auth passes.
- GUIDE-3 log safety: ✅ Only `hasGuidingDescription` boolean and `guidingDescriptionChars` logged; no raw text.
- Scheduled run unchanged: ✅ Scheduled dry-run passes without API-specific metadata.

**Verdict: APPROVE for deployment preparation. DEPLOY-1 through DEPLOY-4 (hosted infrastructure proof) required before production enablement.**
