# 🎨 Art of Clawpilot

An AI-curated, ever-growing virtual art gallery. A three-agent **Squad** (Artist, Critic, Curator) collaborates daily to add a new museum-grade piece to the collection.

- **Frontend:** React + Vite, deployed as an Azure Static Web App
- **Image generation:** MAI-Image-2e on Microsoft Foundry (auth via Managed Identity)
- **Squad orchestration:** [bradygaster/squad](https://github.com/bradygaster/squad)
- **Daily run:** triggered every morning via Clawpilot automation → GitHub Copilot CLI

---

## Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────┐
│ Clawpilot (7am daily cron)  │────▶│ copilot --agent squad    │
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

## Local dev

```bash
npm install
npm run dev
```

## Daily run (manual)

```bash
copilot --agent squad --yolo
git add . && git commit -m "🎨 Daily piece" && git push
```

## Infra

See [`infra/main.bicep`](./infra/main.bicep). Deploys:
- Azure Static Web App (system-assigned Managed Identity)
- Azure Key Vault (RBAC, soft-delete) holding the Foundry endpoint
- Role assignments: SWA MI → `Key Vault Secrets User` + `Cognitive Services User` on the Foundry resource

## Squad members

| Agent | File | Role |
|---|---|---|
| 🖌️ Artist | `.squad/artist.md` | Generates one museum-grade piece per day |
| 📝 Critic | `.squad/critic.md` | Writes a popular-column-style review of the latest piece |
| 🏛️ Curator | `.squad/curator.md` | Assigns pieces to rooms (≤5 each), commissions new styles |

State lives in `data/*.json` so every decision is inspectable in git history.
