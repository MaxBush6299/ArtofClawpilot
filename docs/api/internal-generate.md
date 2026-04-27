# Internal manual generation API

Phase 1 exposes a backend-only Azure Functions route:

```http
POST /api/internal/generate
X-Clawpilot-Key: <api key stored outside the repo>
Content-Type: application/json
```

The function validates `X-Clawpilot-Key` against the Key Vault secret `clawpilot-api-key` with `DefaultAzureCredential`. Never place this value in source, frontend code, or committed settings.

## Request

```json
{
  "requestId": "clawpilot-2026-04-27-a1b2c3",
  "guidingDescription": "Optional Curator advisory context, max 1000 characters.",
  "correlationId": "optional-correlation-id",
  "callerIdentity": "clawpilot-agent"
}
```

- `requestId` is required and becomes `runId=manual-{UTC_DATE}-{requestId}`.
- `guidingDescription` is optional, limited to 1000 characters, and is passed to Curator as advisory context only.
- `callerIdentity` defaults to `clawpilot-agent`.

## Responses

- `202 accepted`: Container Apps Job start request was accepted.
- `200 already_resolved`: best-effort gallery precheck found the derived `runId` in `data/gallery.json`.
- `400 validation_error`: malformed JSON, missing/invalid `requestId`, or oversized description/body.
- `401 unauthorized`: missing or invalid `X-Clawpilot-Key`.
- `503 trigger_failed`: Key Vault, Azure Resource Manager, or Container Apps Job start failed.

The duplicate precheck reads `CLAWPILOT_GALLERY_STATE_URL` when set; otherwise it uses the configured GitHub owner/repo/branch raw `data/gallery.json` URL. If that read is unavailable, Phase 1 still starts the job and relies on orchestrator runId idempotency for exactly-once outcomes.

## Function app settings

Use app settings or Key Vault references for configuration values; do not commit real secrets.

```text
KEY_VAULT_URL=https://<vault>.vault.azure.net
CLAWPILOT_API_KEY_SECRET_NAME=clawpilot-api-key
AZURE_SUBSCRIPTION_ID=<subscription id>
AZURE_RESOURCE_GROUP=<resource group containing the job>
HOSTED_JOB_NAME=<container apps job name>
CONTAINER_APP_JOB_CONTAINER_NAME=runner
GITHUB_OWNER=MaxBush6299
GITHUB_REPO=ArtofClawpilot
GITHUB_BRANCH=main
```

When the Function starts a manual run, it overrides the Container Apps Job execution with:

```text
RUN_DATE_UTC
RUN_ID
TRIGGER_SOURCE=manual-api
REQUEST_ID
CALLER_IDENTITY
CORRELATION_ID
HOSTED_TRACE_ID
GUIDING_DESCRIPTION
```
