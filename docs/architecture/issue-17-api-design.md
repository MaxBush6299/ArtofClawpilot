# Issue #17 API Design: Manual Image Generation Trigger

> **Status:** Design authority for manual image generation API (Phase 1 with future hardening path).
>
> **Current answer to Max:** This document consolidates design decisions from `.squad/decisions.md` entries #32–34 and GitHub issue #17 into a durable reference. The manual image generation API is an internal-only HTTP gateway for the clawpilot agent to request new gallery images outside the scheduled daily run. This design uses Azure Functions (Consumption Plan) as the thin HTTP entry point, Azure Key Vault for API key storage, and the existing hosted ACA Job for orchestration. Phase 1 uses API-key authentication; Phase 2 upgrades to managed identity when clawpilot is deployed as an Azure compute resource.

## Goal, scope, non-goals

### Goal

Enable an internal clawpilot agent caller to request a new generated gallery image via HTTP, with:
- Request idempotency via unique run identity
- Optional guiding description for Curator context
- Same multi-image-per-day support as scheduled runs
- Observability/correlation without leaking sensitive content

### Scope

- Thin HTTP API layer using Azure Functions (POST `/api/internal/generate`)
- Request validation, auth, and pre-checks
- API-key authentication in Phase 1 (API keys stored in Azure Key Vault)
- Direct ACA Job invocation from the Function
- Structured logging with request correlation
- Rate limiting per caller (10 requests/day, 2 concurrent, 10-minute cooldown)
- Phase 1 API key contract and environment wiring

### Out of scope (Phase 2+)

- Multi-tenant admin dashboard
- Public unauthenticated generation
- Managed identity migration (deferred to Phase 2)
- Content moderation or filtering webhooks
- Long-polling or WebSocket response delivery
- Guiding description length hardening beyond MVP validation

## Hosting topology

### Azure components

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Static Web Apps)                                  │
│ - React + Vite                                               │
│ - Read-only gallery display                                  │
│ - No direct API calls                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Azure Functions (Consumption Plan) — NEW for Issue #17      │
│ - POST /api/internal/generate                               │
│ - Auth via X-Clawpilot-Key header                           │
│ - Pre-check gallery.json idempotency                        │
│ - Invoke ACA Job                                             │
│ - Rate limiting via Table Storage                            │
│ - Managed identity for ACA Job start permission             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Azure Key Vault                                              │
│ - clawpilot-api-key secret (Phase 1)                       │
│ - Reasoning and image deployment endpoints (existing)       │
│ - Foundry API keys (existing)                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Azure Container Apps Job (existing, scheduled daily run)    │
│ - Python orchestrator (Curator, Artist, Critic, publish)   │
│ - Container image from ACR                                   │
│ - Manual-triggered in Phase 1, scheduled in Phase 2+        │
│ - Managed identity for Key Vault + GitHub + Foundry        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ GitHub Repository                                            │
│ - data/gallery.json (canonical state)                       │
│ - public/gallery/* (image assets)                            │
│ - Idempotency source of truth                               │
└─────────────────────────────────────────────────────────────┘
```

### Control flow (HTTP request to job invocation)

1. **Clawpilot agent** sends HTTP POST to `/api/internal/generate` with:
   - `X-Clawpilot-Key` header (API key from Key Vault)
   - JSON body: `requestId`, `guidingDescription`, `callerIdentity`, `correlationId`

2. **Azure Function** performs:
   - Auth: validate `X-Clawpilot-Key` against Key Vault secret
   - Rate limit: check Table Storage (10/day, 2 concurrent, 10-min cooldown)
   - Idempotency: pre-check `data/gallery.json` for duplicate `runId`
   - Transform: generate `runId = manual-{runDate}-{uuid-short}`

3. **ACA Job invocation** passes:
   - Environment variables: `RUN_ID`, `TRIGGER_SOURCE=manual-api`, `REQUEST_ID`, `CALLER_IDENTITY=clawpilot-agent`, `CORRELATION_ID`
   - Optional: `GUIDING_DESCRIPTION` (if provided, max 1000 chars)

4. **Orchestrator** runs end-to-end with the injected run identity and optional guiding description.

5. **GitHub push** commits the outcome (image + gallery metadata or skip record).

## Endpoint contract: POST /api/internal/generate

### Request

```http
POST /api/internal/generate HTTP/1.1
Host: api.artofclawpilot.example.com
X-Clawpilot-Key: <api-key-from-key-vault>
Content-Type: application/json

{
  "requestId": "req-2026-04-27-abc123xyz",
  "guidingDescription": "An abstract piece inspired by morning light",
  "callerIdentity": "clawpilot-agent",
  "correlationId": "trace-2026-04-27-789def456",
  "timestamp": "2026-04-27T18:30:00Z"
}
```

### Request fields

| Field | Type | Required | Validation | Notes |
| --- | --- | --- | --- | --- |
| `requestId` | string | yes | alphanumeric, 1–64 chars, no spaces | Used for idempotency. Unique per caller per day. |
| `guidingDescription` | string | no | max 1000 chars, UTF-8 | Optional context for Curator room assignment. Not a prompt override. |
| `callerIdentity` | string | yes | fixed value: `clawpilot-agent` | Identifies the internal caller. No user-provided values. |
| `correlationId` | string | yes | alphanumeric, 1–64 chars | Trace ID for Log Analytics correlation. Provided by caller. |
| `timestamp` | string (ISO 8601) | no | valid ISO 8601 datetime | Request time (server uses current time if omitted). |

### Response: Accepted (HTTP 202)

Request was valid, rate limit OK, and ACA Job invocation started.

```json
{
  "status": "accepted",
  "runId": "manual-2026-04-27-abc123xyz",
  "correlationId": "trace-2026-04-27-789def456",
  "jobExecutionId": "artclaw-daily-job-2pewehrfleuls-xyz123",
  "message": "Image generation triggered. Monitor logs with correlationId for progress."
}
```

### Response: Already Resolved (HTTP 200)

Same `requestId` and `runDate` already processed (idempotency).

```json
{
  "status": "already_resolved",
  "runId": "manual-2026-04-27-abc123xyz",
  "correlationId": "trace-2026-04-27-789def456",
  "existingImage": {
    "id": "img-2026-04-27-manual",
    "title": "An abstract piece inspired by morning light",
    "path": "/gallery/2026/2026-04-27-manual-abc123xyz.png",
    "createdAt": "2026-04-27T18:35:22Z"
  },
  "message": "This request was already processed. Returning existing result."
}
```

### Response: Validation Error (HTTP 400)

Malformed request, missing required fields, or oversized description.

```json
{
  "status": "invalid_request",
  "correlationId": "trace-2026-04-27-789def456",
  "error": {
    "code": "validation_failed",
    "message": "guidingDescription exceeds 1000 characters",
    "field": "guidingDescription",
    "details": {
      "maxLength": 1000,
      "providedLength": 1250
    }
  }
}
```

### Response: Unauthorized (HTTP 401)

Invalid or missing `X-Clawpilot-Key` header.

```json
{
  "status": "unauthorized",
  "error": {
    "code": "invalid_api_key",
    "message": "API key validation failed"
  }
}
```

### Response: Rate Limited (HTTP 429)

Caller exceeded rate limit (10 requests/day, 2 concurrent, 10-min cooldown).

```json
{
  "status": "rate_limited",
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Daily request limit exceeded. Retry after 10 minutes.",
    "retryAfter": 600
  }
}
```

### Response: Service Unavailable (HTTP 503)

ACA Job invocation failed or Key Vault is unreachable.

```json
{
  "status": "service_unavailable",
  "correlationId": "trace-2026-04-27-789def456",
  "error": {
    "code": "job_invocation_failed",
    "message": "Failed to trigger Azure Container Apps Job"
  }
}
```

## Phase 1: Key-based authentication

### Design decision

**Use API keys in Phase 1; defer managed identity to Phase 2.**

**Rationale:**
- Simpler for single-caller MVP (clawpilot agent)
- Avoids complex OAuth2/bearer token flows
- Aligns with existing Key Vault infrastructure
- Lower implementation lift (~1 week vs ~2 weeks for Entra ID)
- Sufficient security posture with RBAC audit trail and rate limiting

### Implementation

1. **Secret storage:** API key stored in Azure Key Vault as `clawpilot-api-key` secret.

   > Source: [Azure Key Vault Secrets client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/keyvault-secrets-readme) — fetched 2026-04-27
   >
   > Use `SecretClient` from `azure-keyvault-secrets` to retrieve and validate the key at Function startup or per-request.

2. **Validation:** Azure Function validates the `X-Clawpilot-Key` header against the Key Vault secret.

   ```python
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient

   credential = DefaultAzureCredential()
   secret_client = SecretClient(vault_url=f"https://{vault_name}.vault.azure.net/",
                                 credential=credential)

   def validate_api_key(request_key: str) -> bool:
       stored_key = secret_client.get_secret("clawpilot-api-key").value
       return request_key == stored_key
   ```

3. **No secrets in repo:** The API key is stored only in Key Vault. Local development uses a test key via environment variable or local vault emulator (not committed to source).

4. **RBAC audit trail:** Function's managed identity has:
   - **Key Vault secret read** permission (to validate the key)
   - **ACA Job start** permission (to invoke the job)
   - **Azure Table Storage write** permission (for rate limit tracking)
   - **Log Analytics send metrics/logs** permission

### Local development handoff for clawpilot agent

When deploying clawpilot (outside this project), the agent retrieves the API key **server-side only**. The agent does **not** embed the key in code.

**Recommended pattern:**
1. Clawpilot queries a secure config service or environment (e.g., Kubernetes secret, Azure App Configuration).
2. At runtime, clawpilot reads the key into memory and caches it.
3. Clawpilot sends HTTP requests with the key in the `X-Clawpilot-Key` header.
4. The key is never logged, hardcoded, or exposed to frontend/client context.

**Sharing the key securely:**
- Do NOT add the key to `.env.local` or `package.json` scripts.
- Create a shared secret in your secure config service (e.g., Azure Key Vault, GitHub Secrets for CI/CD, Kubernetes secret for AKS).
- Document the key location and rotation policy in a separate **ops runbook** (not in this repo).

## Phase 2: Future managed identity migration path

### Design approach

When clawpilot is deployed as an Azure compute resource (Container Apps Job, Function, AKS pod), migrate from API key to **managed identity with bearer token validation**.

### Phase 2 implementation outline

1. **Clawpilot as Azure resource:**
   - Assigned a user-assigned managed identity (same as the ACA Job).
   - Uses `DefaultAzureCredential` from Azure SDK to obtain an access token.

2. **Bearer token in request:**
   - Clawpilot sends `Authorization: Bearer <token>` instead of `X-Clawpilot-Key`.
   - Token is obtained from Azure Entra ID with audience `https://api.artofclawpilot.example.com`.

3. **API validation:**
   - Azure Function decodes and validates the token (issuer, audience, signature).
   - Extracts caller identity from token claims (e.g., object ID, app name).

4. **RBAC simplification:**
   - No per-caller rate limiting needed (RBAC enforces quota).
   - Single identity federation (clawpilot identity = API caller).

> Source: [Use managed identities for App Service and Azure Functions](https://learn.microsoft.com/en-us/azure/app-service/overview-managed-identity) — fetched 2026-04-27
>
> Microsoft documents managed identities as the recommended pattern for Azure-to-Azure authentication.

### Migration trigger

Implement Phase 2 when:
- Clawpilot is deployed as a persistent Azure resource.
- Organizational policy mandates Entra ID for all internal APIs.
- Multi-caller scenarios require RBAC-based quota management.

## Job invocation and environment contract

### Azure Container Apps Job invocation

The Azure Function invokes the ACA Job using the Azure SDK with managed identity. The Function must have the `start` permission on the target job resource.

### Environment variables passed to the job

The Function sets these environment variables when invoking the job:

| Variable | Value | Source | Notes |
| --- | --- | --- | --- |
| `RUN_ID` | `manual-{runDate}-{uuid-short}` | Generated from `requestId` | Idempotency key for orchestrator |
| `TRIGGER_SOURCE` | `manual-api` | Fixed value | Distinguishes from scheduled runs |
| `REQUEST_ID` | `{requestId}` | Caller request | For API correlation |
| `CALLER_IDENTITY` | `clawpilot-agent` | Fixed value | Internal caller identifier |
| `CORRELATION_ID` | `{correlationId}` | Caller request | Trace ID for Log Analytics |
| `GUIDING_DESCRIPTION` | `{guidingDescription}` | Caller request (optional) | Passed to Curator; max 1000 chars |
| `RUN_DATE_UTC` | `{YYYY-MM-DD}` | Current UTC date | Existing; maintains date scoping |

### Orchestrator CLI contract

The Python orchestrator accepts these arguments:

```bash
python3 -m orchestrator.main \
  --repo-root "$REPO_WORKSPACE" \
  --run-date "$RUN_DATE_UTC" \
  --run-id "$RUN_ID" \
  --trigger-source "$TRIGGER_SOURCE" \
  --guiding-description "$GUIDING_DESCRIPTION"
```

All arguments are optional or have sensible defaults (e.g., `--run-date` defaults to current UTC date if not provided).

### Orchestrator handling of guiding description

- **Curator receives** the description as context, not as a prompt override.
- **Curator owns room assignment** using the description as advisory input.
- **Not logged as plain text** — only `guidingDescriptionPresent: boolean` and description length logged.
- **Excluded from published gallery** — the description is internal context only.

## Observability and security

### Structured logging

The Function and orchestrator log structured events to Log Analytics. Every request is traceable via `correlationId`.

#### Function-side logging

```json
{
  "timestamp": "2026-04-27T18:30:05Z",
  "correlationId": "trace-2026-04-27-789def456",
  "requestId": "req-2026-04-27-abc123xyz",
  "event": "api_request_received",
  "caller_identity": "clawpilot-agent",
  "auth_result": "valid",
  "rate_limit_check": "passed",
  "idempotency_check": "new_request",
  "job_invocation_status": "started",
  "jobExecutionId": "artclaw-daily-job-2pewehrfleuls-xyz123"
}
```

#### Security: what NOT to log

- ❌ Raw `X-Clawpilot-Key` header value
- ❌ Full `guidingDescription` text (use boolean flag and length only)
- ❌ GitHub App credentials or Foundry API keys
- ❌ Raw gallery contents (summary counts OK)

#### Orchestrator-side logging (existing, preserved)

- ✅ `runId`, `triggerSource`, `requestId` (links to API request)
- ✅ `correlationId` (trace correlation)
- ✅ Phase progression (Curator → Artist → Critic → publish)
- ✅ Asset paths and image IDs

### Rate limiting implementation

Rate limits are tracked in **Azure Table Storage** with per-caller buckets.

- **Limit:** 10 requests/day per caller
- **Concurrent:** 2 simultaneous executions
- **Cooldown:** 10-minute penalty after limit exceeded

**Table schema:**

```
PartitionKey: "{caller_identity}"
RowKey: "{date}-{sequence}"
Columns:
  - request_count (int)
  - last_reset_time (datetime)
  - in_progress_count (int)
  - last_limit_exceeded_time (datetime)
```

### Idempotency check (pre-check, no mutation)

Before invoking the ACA Job, the Function:

1. Clones or pulls the latest `data/gallery.json` from GitHub.
2. Computes `runId = manual-{runDate}-{uuid-short}`.
3. Checks for existing `runId` in gallery or skip records.
4. If found, returns HTTP 200 `already_resolved` with existing record (fast response).
5. If not found, proceeds with rate limit and job invocation.

**Benefit:** Prevents wasted job executions for duplicate requests and provides immediate feedback.

## Validation and deployment gates

### Acceptance criteria

Butters (test lead) will validate these scenarios before Phase 1 sign-off:

1. **API key validation (AUTH-1):** Invalid/missing `X-Clawpilot-Key` returns HTTP 401.
2. **API key validation (AUTH-2):** Valid `X-Clawpilot-Key` from Key Vault returns HTTP 202.
3. **Rate limit enforcement (RATE-1):** After 10 requests/day, returns HTTP 429.
4. **Rate limit enforcement (RATE-2):** Multiple concurrent requests (> 2) queue or return 429.
5. **Idempotency (IDEM-1):** Identical `requestId` + `runDate` returns HTTP 200 `already_resolved`.
6. **Idempotency (IDEM-2):** Distinct `requestId` same `runDate` generates distinct images (no overwrite).
7. **Concurrent safety (CONC-1):** Two simultaneous requests complete without gallery corruption.
8. **Log correlation (LOG-1):** Request `correlationId` appears in Log Analytics query for all Function and orchestrator logs.
9. **Guiding description validation (GUIDE-1):** Oversized description (> 1000 chars) returns HTTP 400.
10. **Guiding description safety (GUIDE-2):** Description is not logged as plain text; only presence flag and length logged.

### Deployment gates

Before merging Phase 1 to `main`:

- [ ] Local testing: all acceptance tests MR-1–MR-10 pass.
- [ ] Code review: Stan (lead) approves API contract and security model.
- [ ] Bicep validation: `az bicep validate` and `az deployment group create --what-if` succeed.
- [ ] Hosted smoke: Phase B idempotent rerun validation passes on `hosted-smoke` branch.
- [ ] Log Analytics: correlation queries work and no raw secrets visible.
- [ ] Orchestrator integration: `--guiding-description` argument accepted and passed to Curator.

### Production promotion gates

After Phase 1 merge:

- [ ] One week of production monitoring (API key rotations, rate limit triggers, error rates).
- [ ] No data corruption in gallery records.
- [ ] Trace correlation working end-to-end in production Log Analytics.
- [ ] Clawpilot agent successfully invokes API and receives images.

## Sources

Microsoft Learn documentation (fetched 2026-04-27):

- [Azure Functions security concepts](https://learn.microsoft.com/azure/azure-functions/security-concepts) — Covers API key vs. managed identity tradeoffs, RBAC permissions, and app-level isolation.
- [Work with access keys in Azure Functions](https://learn.microsoft.com/azure/azure-functions/function-keys-how-to) — Explains Function HTTP authorization levels and key-based access control patterns.
- [Use managed identities for App Service and Azure Functions](https://learn.microsoft.com/en-us/azure/app-service/overview-managed-identity) — Documents managed identity setup, token retrieval, and Phase 2 migration guidance.
- [Azure Key Vault Secrets client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/keyvault-secrets-readme) — Code examples for `SecretClient`, key retrieval, and authentication patterns.
- [Jobs in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/jobs) — Documents job trigger types, direct invocation, and execution environment setup.
- [Azure Container Apps managed environment networking](https://learn.microsoft.com/azure/container-apps/environment) — Optional: Phase 2 private endpoint guidance for API isolation.

## Appendix: Sample code patterns

### Function: Key validation

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import azure.functions as func

def validate_api_key(request: func.HttpRequest, vault_url: str) -> bool:
    api_key = request.headers.get("X-Clawpilot-Key")
    if not api_key:
        return False

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    stored_key = client.get_secret("clawpilot-api-key").value

    return api_key == stored_key
```

### Function: ACA Job invocation

```python
from azure.containerappsjobs import ContainerAppsJobsClient
from azure.identity import DefaultAzureCredential

def invoke_job(job_name: str, env_vars: dict) -> str:
    credential = DefaultAzureCredential()
    client = ContainerAppsJobsClient(
        subscription_id=subscription_id,
        credential=credential
    )

    execution = client.job_execution.start(
        resource_group_name=resource_group,
        job_name=job_name,
        # Pass env_vars as overrides or in job definition
    )

    return execution.name  # execution ID
```

### Orchestrator: Accept guiding description

```python
# In orchestrator/main.py or orchestrator/contracts.py

@dataclass
class ExecutionContext:
    run_date: str
    run_id: str
    trigger_source: str
    guiding_description: Optional[str] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None

# In curator.py, Curator.select_room() receives guiding_description:
def select_room(
    gallery: GalleryState,
    guiding_description: Optional[str] = None
) -> RoomBrief:
    # Use guiding_description as advisory context, not override
    # Curator still owns final room assignment
    room_brief = self.reasoning_client.call_curator(
        context=guiding_description,
        gallery_context=gallery
    )
    return room_brief
```

---

**Document authored by:** Cartman, Solution Engineer Consultant
**Date:** 2026-04-27
**Next steps:** Kyle + Tolkien Phase 1 implementation (~1 week); Butters acceptance test design; Stan Phase 1 review gate.
