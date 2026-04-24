# 🎨 Art of Clawpilot

An AI-curated, ever-growing virtual art gallery. A three-agent **Squad** (Artist, Critic, Curator) collaborates daily to add a new museum-grade piece to the collection.

- **Frontend:** React + Vite, deployed as an Azure Static Web App
- **Reasoning (hosted target):** `grok-4-20-reasoning` on Microsoft Foundry
- **Image generation:** MAI-Image-2e on Microsoft Foundry (auth via Managed Identity)
- **Squad orchestration:** [bradygaster/squad](https://github.com/bradygaster/squad)
- **Daily run:** triggered every morning via Clawpilot automation → GitHub Copilot CLI

---

## Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────┐
│ Clawpilot (7am daily cron)  │────▶│ copilot --agent squad -p │
└─────────────────────────────┘     │  • Curator: assign room  │
                                    │  • Critic:  review last  │
                                    │  • Artist:  generate new │
                                    └────────────┬─────────────┘
                                                 │ git push
                                                 ▼
                                    ┌──────────────────────────┐
                                    │ GitHub Action            │
                                    │  → Azure Static Web App  │
                                    └──────────────────────────┘
```

Hosted target-state design: [`docs/architecture/hosted-daily-run.md`](./docs/architecture/hosted-daily-run.md)

Hosted execution plan: [`docs/architecture/hosted-execution-plan.md`](./docs/architecture/hosted-execution-plan.md)

Microsoft-specific hosted architecture choices in that design are grounded in Microsoft Learn.

## Local dev

```bash
npm install
npm run dev
```

## Daily run (manual)

```bash
python -m orchestrator.main --repo-root .
```

Local dry run:

```bash
python -m orchestrator.main --repo-root . --dry-run --allow-dirty
```

## Infra

See [`infra/main.bicep`](./infra/main.bicep). Deploys:
- Azure Static Web App (system-assigned Managed Identity)
- Azure Key Vault (RBAC, soft-delete) for hosted runner config and secrets
- Log Analytics + Azure Container Apps managed environment
- User-assigned Managed Identity for the hosted daily runner
- Azure Container Apps Job shell for the hosted runner (manual-first until hosted smoke passes)
- Role assignments: job MI → `Key Vault Secrets User`, `Cognitive Services User`, and optional `AcrPull`

The hosted daily-run target state is documented in [`docs/architecture/hosted-daily-run.md`](./docs/architecture/hosted-daily-run.md).
The cutover smoke procedure is documented in [`docs/architecture/hosted-smoke-checklist.md`](./docs/architecture/hosted-smoke-checklist.md).

## Hosted foundation slice

This repo now includes the first hosted execution foundation for issues #3, #4, #5, and #12:

- `infra/main.bicep` provisions the Container Apps environment, a manual-or-scheduled job shell, and user-assigned managed identity.
- `scripts/hosted-bootstrap.mjs` mints a GitHub App installation token, clones a fresh workspace, runs the Python orchestrator by default, and can push resulting changes.
- `Dockerfile` packages the hosted bootstrap shell plus the Python orchestrator path used by the Container Apps Job.
- Hosted Foundry config now keeps the reasoning chat endpoint separate from the MAI image-generation endpoint while still treating deployment names as runtime config.

Issue #15 adds the cutover-proof surface:

- `jobTriggerType` keeps the ACA Job manual until the smoke gate passes.
- `hostedRunDateOverride` makes same-day replay/idempotency proof repeatable.
- `hosted-smoke-checklist.md` defines the hosted auth probe, durable smoke-branch publish proof, failure-path proof, and promotion bar.

Microsoft-specific choices follow Microsoft Learn guidance for:

- Azure Container Apps Jobs schedules in UTC and `Microsoft.App/jobs` managed-identity/Bicep support
- Key Vault references in Container Apps with RBAC and managed identity
- Managed identity / Microsoft Entra ID access for Azure AI Foundry calls

Local smoke checks:

```bash
npm run hosted:bootstrap -- --help
python -m orchestrator.main --help
docker build -t art-of-clawpilot-runner .
```

## Squad members

| Agent | File | Role |
|---|---|---|
| 🖌️ Artist | `.squad/artist.md` | Generates one museum-grade piece per day |
| 📝 Critic | `.squad/critic.md` | Writes a popular-column-style review of the latest piece |
| 🏛️ Curator | `.squad/curator.md` | Assigns pieces to rooms (≤5 each), commissions new styles |

State lives in `data/*.json` so every decision is inspectable in git history.
