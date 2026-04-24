# History - Wendy

## Seed Context

- Requested by Max Bush.
- Project: Art of Clawpilot, an AI-powered virtual art gallery that adds one new piece each day.
- Stack: React + Vite frontend, Python orchestration/runtime, Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, Azure Static Web Apps.
- Current issue focus: #2, the hosted daily-run architecture and execution contract.

## Learnings

- Wendy owns React UI and gallery experience work for this repo.
- Issue #15 frontend sign-off is compatible with the hosted smoke plan because the UI reads only published room image entries from `data/gallery.json`, ignores top-level `skipped[]`, and tolerates optional image audit fields like `promptSummary`, `runDate`, and `reasoningModel`.
