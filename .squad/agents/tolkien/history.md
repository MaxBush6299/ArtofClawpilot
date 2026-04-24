# History - Tolkien

## Seed Context

- Requested by Max Bush.
- Project: Art of Clawpilot, an AI-powered virtual art gallery that adds one new piece each day.
- Stack: React + Vite frontend, Python orchestration/runtime, Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, Azure Static Web Apps.
- Current issue focus: #2, the hosted daily-run architecture and execution contract.

## Learnings

- Tolkien owns Azure platform work: Container Apps Jobs, Key Vault, SWA, and hosted runtime wiring.
- 2026-04-24 foundation start lands a user-assigned managed identity for the hosted daily runner, with Key Vault + Foundry access moved onto the job rather than the Static Web App.
- 2026-04-24 hosted bootstrap now uses a GitHub App installation token to clone a fresh workspace, optionally run a command, and push from an ephemeral checkout when enabled.
- 2026-04-24 the hosted container contract is `node scripts/hosted-bootstrap.mjs`, with Azure Container Apps injecting Key Vault-backed secrets and `AZURE_CLIENT_ID` for the job identity.
- 2026-04-24 hosted Foundry runtime config must keep separate reasoning and MAI endpoints: reasoning uses the Azure OpenAI chat surface, while MAI image generation uses `https://<resource>.services.ai.azure.com/mai/v1/images/generations`.
- 2026-04-24 issue #8/#9 follow-through keeps deployment names as injected runtime config (`FOUNDRY_REASONING_DEPLOYMENT`, `FOUNDRY_IMAGE_DEPLOYMENT`) and keeps hosted auth on managed identity / Entra rather than API keys.
- 2026-04-24 Foundry transport classification now needs to split auth, deployment/endpoint, content-filter, and malformed-response cases inside `orchestrator/integrations/foundry.py`, with infra wiring in `infra/main.bicep` and Node image fallback wiring in `scripts/kv-client.mjs`.
- 2026-04-24 issue #13 platform slice standardizes hosted diagnostics on one JSON log line per event from both `scripts/hosted-bootstrap.mjs` and `orchestrator/main.py`, so ACA Job stdout/stderr lands queryable in Log Analytics with phase/event/runDate correlation.
- 2026-04-24 real Azure-hosted smoke/integration proof is still deferred to issue #15; current validation evidence for hosted diagnostics is local syntax/build plus deterministic orchestrator dry-run fixtures.
- 2026-04-24 issue #15 platform follow-through keeps the ACA Job manual-first with an explicit `jobTriggerType`, adds `hostedRunDateOverride` for same-day replay proof, and treats durable smoke on a disposable branch as the cutover gate before scheduling `main`.
- 2026-04-24 issue #15 live smoke proved the ACA stack now exists in `rg-evaldemo` (`artclaw-daily-job-2pewehrfleuls`, `artclaw-acae-2pewehrfleuls`, `artclaw-job-mi-2pewehrfleuls`, `artclaw-logs-2pewehrfleuls`) and the runner image is published in `evalt1acr.azurecr.io/artofclawpilot-runner:latest`.
- 2026-04-24 Container Apps Job Key Vault secret references require an explicit `identity` field per secret; omitting it makes the job deployment fail with `ContainerAppSecretInvalid`.
- 2026-04-24 smoke can reach the real hosted boundary even before GitHub auth is wired; Log Analytics showed the runner container start and `hosted-bootstrap` fail in `config` with `Missing required environment variable: GITHUB_APP_ID`, which is the current hosted blocker.
- 2026-04-24 live reasoning calls succeed against `https://eval-t1.openai.azure.com` with the `grok-4-20-reasoning` deployment, but the MAI project endpoint at `https://eval-t1.services.ai.azure.com/api/projects/eval-t1-project/mai/v1/images/generations` now hard-fails without an explicit supported `api-version`, so image generation remains blocked on runtime config/API-contract alignment.
