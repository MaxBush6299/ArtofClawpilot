# Hosted daily-run architecture

> Status: proposed target state for issue #2.

Art of Clawpilot currently depends on a desktop-triggered `copilot --agent squad` session. The hosted target state replaces that runtime dependency with one scheduled Azure Container Apps Job that runs a Python orchestrator, executes Curator, Critic, and Artist as logical role steps, and publishes one durable daily outcome to GitHub.

## Microsoft Learn grounding

All Microsoft-specific implementation work for this design should be grounded in Microsoft Learn. This document relies on the following Learn guidance:

- Azure Container Apps scheduled jobs use cron expressions evaluated in UTC, which matches the hosted run's day-scoped UTC contract: [Azure Container Apps jobs - Job trigger types](https://learn.microsoft.com/azure/container-apps/jobs#job-trigger-types)
- The `Microsoft.App/jobs` resource supports scheduled job configuration and user-assigned managed identity in Bicep: [Microsoft.App/jobs Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/jobs#property-values)
- Microsoft recommends Microsoft Entra ID or managed identities over stored credentials for Azure AI calls: [Azure AI Foundry chat completions quickstart](https://learn.microsoft.com/azure/ai-foundry/openai/chatgpt-quickstart#set-up)
- Foundry deployments are called by deployment name, and deployment names should be treated as first-class config: [Create and deploy an Azure OpenAI resource - Deploy a model](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/create-resource#deploy-a-model)
- `grok-4-20-reasoning` is an available reasoning model in Microsoft Foundry Models, while image generation remains on the separate `MAI-Image-2e` deployment: [Foundry models sold directly by Azure - xAI models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure#xai-models-sold-directly-by-azure)

---

## Problem statement

The current daily run is not hostable because the runtime contract lives inside an interactive Copilot CLI flow. Infra cannot provision a stable execution surface, backend work has no concrete runtime boundary for role logic, and test work cannot validate the run-identity-scoped idempotency invariant independently of a desktop session.

The hosted design needs to:

- remove runtime dependence on `copilot --agent squad`
- keep the run-identity invariant: exactly one new image or exactly one structured skip record per unique run identity (via `runId`), while allowing multiple images per calendar day with distinct `runId` values
- keep GitHub as the published source of truth for `data/*.json` and `public/gallery/*`
- separate infrastructure, orchestration, Foundry, GitHub, and deployment ownership cleanly

## Proposed architecture

### Target components

| Component | Runtime home | Responsibility | Out of scope |
| --- | --- | --- | --- |
| Azure Container Apps Job | Azure | Scheduled execution, retry policy, logs, managed identity attachment | Gallery logic, prompt design |
| Python orchestrator | Job container | Runs the daily workflow end to end | Provisioning Azure resources |
| Curator step | Python module inside orchestrator | Selects target room, style request, and run brief | Image generation |
| Critic step | Python module inside orchestrator | Reviews the latest published piece when one exists and emits critique plus suggestion | Publishing to GitHub |
| Artist step | Python module inside orchestrator | Builds the image brief, calls image generation, validates the result | Room assignment policy |
| Microsoft Foundry reasoning deployment | External Azure AI resource | Hosts `grok-4-20-reasoning` for Curator/Critic reasoning and any prompt-refinement step that needs an LLM | Final image synthesis |
| Microsoft Foundry image deployment | External Azure AI resource | Hosts `MAI-Image-2e` for the final image generation call and returns image bytes plus image-model metadata | Repo writes, orchestration |
| GitHub repository | External system of record | Stores `data/*.json`, `public/gallery/*`, commit history, and triggers deployment | Role execution |
| Azure Static Web Apps | GitHub-triggered deploy target | Builds and serves the frontend from repo contents | Daily orchestration |

### Runtime shape

The hosted runtime is one orchestrator process, not three spawned agents. Curator, Critic, and Artist remain named concepts, but they execute as ordered functions inside the same Python process so the run has one config surface, one auth surface, one log stream, and one publication transaction.

### Recommended code layout

The repo does not have to adopt this exact naming, but the hosted work should land in a shape close to:

```text
orchestrator/
  main.py
  config.py
  contracts.py
  state/
    load.py
    validate.py
  roles/
    curator.py
    critic.py
    artist.py
  integrations/
    foundry.py
    github_repo.py
  publish/
    commit.py
    idempotency.py
```

## Daily execution sequence

1. The Container Apps Job runs with concurrency set to one active replica. During cutover proof it should stay on a manual trigger; after promotion it moves to the daily schedule, which Microsoft Learn evaluates in UTC.
2. The job authenticates with a user-assigned managed identity.
3. The job shell (`node scripts/hosted-bootstrap.mjs`) mints a GitHub App installation token, clones a fresh workspace, and runs `python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE"` inside that checkout.
4. The orchestrator loads config from explicit environment variables / CLI args, reads secrets from Key Vault, and resolves the current logical `runDate` in UTC.
5. The orchestrator validates `data/gallery.json`, `data/critiques.json`, and `data/next-brief.json`.
6. The orchestrator checks idempotency: if the provided `runId` already appears in the gallery (published image) or skip records, the run exits cleanly without mutation. If `runDate` has a skip record (from any prior run identity), the day is considered closed and the run exits before any model call.
7. The Curator step uses the deployed `grok-4-20-reasoning` reasoning deployment to select the target room and emit the structured brief for today.
8. If a prior published image exists, the Critic step uses `grok-4-20-reasoning` to write a critique of that latest piece and a suggestion that can influence the next brief.
9. The Artist step assembles the final image brief and calls the `MAI-Image-2e` deployment by managed identity for image generation.
10. One of two domain outcomes is assembled in memory:
    - **publish outcome:** one image asset plus one gallery metadata entry
    - **skip outcome:** one structured skip record and no image asset
11. The orchestrator validates the write set, and the bootstrap shell creates one git commit for the day and pushes it to `main`.
12. The push triggers the existing GitHub-to-Static-Web-App deployment flow, which rebuilds the site from the committed repo state.

## Execution contract

### Inputs

The orchestrator requires these inputs at run start:

- repo target: GitHub owner, repo, branch (`main`)
- run date: UTC calendar date (used for grouping and asset naming; may have multiple images with distinct run identities)
- run identity: unique run identifier (e.g., `scheduled-{runDate}` for scheduled runs, or `manual-{runDate}-{uuid}` for manual API runs) used as the idempotency key
- persisted state: `data/gallery.json`, `data/critiques.json`, `data/next-brief.json`
- reasoning model config: Azure OpenAI-compatible reasoning endpoint, `grok-4-20-reasoning` deployment name, API version
- image model config: MAI image-generation endpoint, `MAI-Image-2e` deployment name, image settings
- GitHub auth config: GitHub App identifiers and installation target
- prompt/config assets for Curator, Critic, and Artist logic

In the hosted path, these inputs are passed non-interactively through Container Apps Job environment variables and Key Vault-backed secret references. The bootstrap shell injects `REPO_WORKSPACE` and `RUN_DATE_UTC` into the Python process so the orchestrator can run against the fresh clone without relying on interactive state.

Deployment names, not raw model names, should be treated as runtime config because Microsoft Learn documents deployment names as the contract used in code. The hosted job should inject separate reasoning and image endpoints so the Azure OpenAI chat surface and the MAI image-generation surface cannot be confused at runtime.

### Role-step contract

| Step | Inputs | Outputs |
| --- | --- | --- |
| Curator | `gallery.json`, prior `next-brief.json`, run date, `grok-4-20-reasoning` deployment | target room id, style request, artist brief |
| Critic | latest published image metadata, prior critiques, `grok-4-20-reasoning` deployment | critique entry for the latest image, suggestion text |
| Artist | curator brief, optional critic suggestion, room context, `MAI-Image-2e` deployment | image bytes or structured generation failure |

### Success contract

A successful published run must create exactly these durable effects for the given `runId`:

1. one new image file under `public/gallery/`
2. one new image metadata entry appended to exactly one room in `data/gallery.json` (with `runId` included)
3. zero new skip records for that same `runDate`
4. optional supporting updates in `data/critiques.json` and `data/next-brief.json`
5. one commit pushed to `main`

Recommended asset path pattern:

```text
public/gallery/YYYY/YYYY-MM-DD-{runId-suffix}.png
```

Required image metadata fields in `data/gallery.json`:

- `id`: stable run-scoped identifier, for example `img-2026-04-24`
- `runId`: unique run identity (e.g., `scheduled-2026-04-24` or `manual-2026-04-24-abc123`)
- `title`
- `path`
- `createdAt`
- `promptSummary`
- `artistNote`
- `criticism` (optional cached excerpt)
- `runDate`
- `model` (`MAI-Image-2e` deployment used for the published image)
- `reasoningModel` (optional audit field for the `grok-4-20-reasoning` deployment used during curation/critique)

### Structured skip contract

A structured skip is the durable fallback when orchestration completes but the system intentionally decides not to publish an image for that `runId`. A skip must create exactly these durable effects:

1. no new file under `public/gallery/`
2. one new skip record in `data/gallery.json` (with `runId` included)
3. no new image metadata entry for that `runId`
4. one commit pushed to `main`

Recommended top-level addition to `data/gallery.json`:

```json
{
  "version": 1,
  "rooms": [],
  "skipped": []
}
```

Required skip fields:

- `id`: stable run-scoped identifier, for example `skip-2026-04-24`
- `runId`: unique run identity that was skipped (e.g., `scheduled-2026-04-24` or `manual-2026-04-24-abc123`)
- `runDate`
- `stage`: `curator`, `critic`, `artist`, or `publish`
- `reasonCode`: controlled value such as `foundry_generation_failed`, `content_filtered`, `validation_failed`
- `message`
- `createdAt`
- `retryable`: boolean
- `error`: structured error payload with `code`, `message`, and optional machine-readable `details`
- `creativeContext` (recommended whenever generation was attempted): room/brief/prompt-summary metadata that makes the skip reviewable later without replaying the run

### Persistence contract

| Path | Durable purpose | Written on publish | Written on skip |
| --- | --- | --- | --- |
| `data/gallery.json` | Canonical gallery state, room membership, published image metadata, and skip ledger | Yes | Yes |
| `data/critiques.json` | Critic column entries for previously published pieces | Usually | Optional |
| `data/next-brief.json` | Hand-off brief for the next run | Yes | Usually |
| `public/gallery/*` | Published image assets served by the frontend | Yes | No |

## Daily invariant and idempotency rules

The system invariant is day-scoped, not process-scoped: the canonical repo history must contain exactly one durable outcome for each logical run date, either one new image or one structured skip record.

To enforce that invariant:

- the orchestrator uses `runId` as the primary idempotency key
- both image ids and skip ids are scoped by `runId`
- the job checks the repo before any mutation
- retries of the same `runId` are allowed and exit as `already_resolved` with no model calls
- distinct `runId` values on the same `runDate` are permitted and each produces a separate publish outcome
- if a skip record exists for the `runDate`, all further runs for that day exit `day_already_closed` before any model call, regardless of `runId`

## Failure behavior

### Failures that become structured skips

These are controlled domain failures where the orchestrator still has enough context and repo access to close the day cleanly:

- Foundry image generation fails after request submission
- Foundry returns filtered or unusable output
- final image validation fails

### Failures that remain execution failures

These failures do **not** create a skip record because the system cannot safely guarantee a durable publication transaction:

- cannot authenticate to Azure, Key Vault, Foundry, or GitHub
- cannot fetch or push the repo
- input JSON is corrupted beyond safe automated repair
- branch head changes repeatedly and bounded rebase/push retry is exhausted

In these cases the job exits non-zero, emits telemetry, and relies on retry or human intervention. The day is not complete until a later attempt records one durable outcome.

### Operational diagnostics

The Python runner should emit one JSON log line per significant event so Azure Container Apps Jobs and Log Analytics can filter by machine-readable fields instead of desktop-only console text.

Recommended log fields:

- `timestamp`
- `level`
- `phase` (`config`, `pre_run`, `validation`, `git`, `curator`, `critic`, `artist`, `image_generation`, `publish`, `result`)
- `event`
- `runDate`
- `runId`
- `traceId`
- phase-specific diagnostics such as `reasonCode`, `exitCode`, `changedPaths`, `responseId`, and call counts

Operator workflow:

1. filter the job execution logs by `runDate` or `traceId`
2. find the highest-severity record for that execution
3. use `phase` plus `event` to determine whether the stop happened in validation, a role step, image generation, or git/write-set handling
4. use `reasonCode`, `errorCode`, and any attached details to decide retry vs manual intervention

### Deployment failures

GitHub push is part of the publication transaction. Static Web App deployment is downstream and asynchronous. If the push succeeds but the GitHub Action deployment fails, the daily run still counts as published because the canonical repo state is correct; deployment recovery happens by rerunning the workflow, not by rerunning the orchestrator.

## Hosted observability and diagnostics

The hosted runner should emit one structured JSON log line per significant event to stdout/stderr so Azure Container Apps Jobs can forward it directly into Log Analytics. Each record should carry, at minimum:

- `component`: `hosted-bootstrap` or `orchestrator`
- `phase`: `config`, `pre_run`, `curator`, `critic`, `artist`, `publish`, `git`, `runner`, or `auth`
- `event`: stable event name such as `run_started`, `reasoning_call_completed`, `failure_classified`, `write_set_validated`, `already_resolved`, or `push_completed`
- `runDate`, `runId`, and `traceId` for correlation across bootstrap and orchestrator logs
- failure fields when relevant (`reasonCode`, `errorCode`, `exitCode`, `retryable`)

This shape keeps the log body readable in raw ACA Job log streams while also making KQL filters straightforward in `ContainerAppConsoleLogs_CL`.

For parity, the bootstrap shell should stamp the same `runDate`, `runId`, `traceId`, and ACA execution metadata onto its own JSON logs and forward those into `python -m orchestrator.main` (for example via `HOSTED_TRACE_ID` and `HOSTED_RUN_ID`). Bootstrap `run_failed` records should also include machine-usable failure fields such as `errorCode`, `exitCode`, `command`, and a redacted stderr/stdout excerpt so git/auth/bootstrap failures can be triaged without replaying the container locally.

### Azure operator workflow

Per Microsoft Learn, scheduled Container Apps Jobs write console output to the environment's configured logging provider, which is Log Analytics by default. Operators should use the ACA Job execution history to find the execution name, then query `ContainerAppConsoleLogs_CL` by the execution/container group prefix for full run output.

Representative KQL for one hosted run:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerGroupName_s startswith "<job-execution-name>"
| project TimeGenerated, ContainerGroupName_s, ContainerName_s, Log_s
| order by TimeGenerated asc
```

For platform failures (startup, image pull, replica timeout), pair console logs with `ContainerAppSystemLogs_CL` for the same job execution or environment.

## Integration testing status

Hosted diagnostics work now has a repeatable local proof command (`npm run orchestrator:proof`) that drives the real orchestrator through deterministic publish, skip, malformed-output, budget-overflow, and no-op scenarios against disposable repo clones. Before cutover, the job should stay in a manual-first profile and pass the hosted smoke procedure in [`hosted-smoke-checklist.md`](./hosted-smoke-checklist.md); only then does the scheduler become the primary runtime.

## Auth and write-path recommendations

### GitHub write path

**Recommendation:** use a GitHub App installation token and perform a normal git commit plus git push directly to `main`.

Why this is the recommended v1 path:

- one atomic commit can include JSON changes plus binary asset changes
- Git history remains the single publication ledger
- the push naturally triggers Static Web App deployment
- it avoids long-lived PATs in Azure

Alternative considered:

- **Contents API or pull request flow:** safer for heavily protected repos, but it turns publication into a multi-step async workflow and weakens the one-transaction daily contract

### Azure auth path

**Recommendation:** attach one user-assigned managed identity to the Container Apps Job and grant that identity:

- `Key Vault Secrets User` on the project Key Vault
- `Cognitive Services User` on the Foundry resource

This follows Microsoft Learn guidance to prefer managed identity or Microsoft Entra ID auth for Azure AI calls and to use Azure RBAC with Key Vault. Use Key Vault for GitHub App private key material and non-secret config that must stay out of source-controlled job settings. The Static Web App does not need runtime access to Foundry for this hosted design; the job identity owns generation-time auth.

### Hosted runtime boundary

The deployment shell and the runtime logic stay separate on purpose:

- **Job/container entrypoint:** `node scripts/hosted-bootstrap.mjs`
- **Hosted command inside the fresh clone:** `python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE"`

This keeps GitHub App checkout/push behavior in the platform-owned shell while making the actual daily workflow a single Python orchestrator process with one explicit config surface.

## Ownership boundaries

| Area | Primary owner | Contract |
| --- | --- | --- |
| Bicep and Azure job shell | Platform | Provision job, identity, Key Vault wiring, logs, schedule, and deployment permissions |
| Python orchestrator and contracts | Backend | Implement role steps, validation, idempotency, and publication transaction |
| Prompt/content logic for Curator, Critic, Artist | Backend with lead review | Preserve role intent while removing CLI dependence |
| Frontend consumption of `data/*.json` and `public/gallery/*` | Frontend | Read published contracts only; do not infer unpublished state |
| Acceptance validation and failure cases | Test | Validate one-outcome-per-day behavior and idempotent retries |

## What changes

- hosted execution moves from desktop Clawpilot automation to Azure Container Apps Job
- runtime logic moves from interactive Squad prompts to Python role modules
- hosted reasoning standardizes on the deployed `grok-4-20-reasoning` model in Microsoft Foundry
- hosted image generation remains on `MAI-Image-2e`
- the job, not the frontend, becomes the runtime consumer of Key Vault and Foundry auth
- `data/gallery.json` grows a durable skip ledger

## What stays the same

- GitHub remains the published source of truth
- the site still deploys from repo contents through Static Web Apps
- the gallery continues to render from `data/*.json` and `public/gallery/*`
- Curator, Critic, and Artist remain the conceptual roles of the daily ritual

## Assumptions and non-blocking questions

No blocking clarification is required to start infra and app work. This design assumes:

- direct push to `main` by a GitHub App is allowed for the automation identity
- the logical run date is based on UTC unless product direction explicitly needs a gallery-local timezone
- Microsoft-specific infra and SDK implementation details will continue to cite Microsoft Learn during delivery work
- one published image per day is enough for v1; multi-candidate selection is deferred

If branch protection later disallows direct app pushes to `main`, the fallback is an automation branch plus PR merge path, but that should be treated as a deliberate scope change because it weakens the single-transaction publish contract.
