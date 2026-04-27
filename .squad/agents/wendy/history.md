# History - Wendy

## Seed Context

- Requested by Max Bush.
- Project: Art of Clawpilot, an AI-powered virtual art gallery that adds one new piece each day.
- Stack: React + Vite frontend, Python orchestration/runtime, Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, Azure Static Web Apps.
- Current issue focus: #2, the hosted daily-run architecture and execution contract.

## Learnings

- Wendy owns React UI and gallery experience work for this repo.
- Issue #15 frontend sign-off is compatible with the hosted smoke plan because the UI reads only published room image entries from `data/gallery.json`, ignores top-level `skipped[]`, and tolerates optional image audit fields like `promptSummary`, `runDate`, and `reasoningModel`.
- **2026-04-27:** Created `docs/architecture/frontend-hosted-update-guide.md` as the practical implementation guide for Max. Key findings: Home.tsx and Room.tsx require zero changes; both already tolerate `skipped[]` and optional fields via defensive reads (`??.` operators and optional chaining). Frontend is read-only consumer of orchestrator output; validation is owned by backend. Skip records are operational artifacts not displayed to users. Type safety can be added later if strict mode is adopted; not required for smoke proof. Concrete validation checklist tied to Phase B/C of hosted smoke procedure in `hosted-smoke-checklist.md`.
- **2026-04-27 feedback (Butters review):** Initial draft rejected for five inaccuracies: `runDate` overclaimed as full ISO 8601 instead of `YYYY-MM-DD` day key; `Room.tsx` criticism misdescribed as optional chaining vs. actual truthy check; static JSON import overclaimed as build-time schema validation; Home cover incorrectly assumed to be newest image; contract boundaries conflated data validation with tolerance. **Stan revised the guide; Butters approved after corrections verified.**
