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
- **2026-04-27 gallery diagnosis (user terminology confusion):** Max reported "new image overwrote existing agents" after hosted runner execution. **ROOT CAUSE: Terminology mismatch, not a data bug.** Gallery history analysis reveals: (1) `data/gallery.json` was initialized with empty `room-01.images[]` in commit fc2756e, (2) room remained empty through commit f827d6e, (3) commit e5c07c5 (hosted runner) correctly **appended** the first image `scheduled-2026-04-27` to the array, (4) no prior gallery images existed to overwrite. **Evidence:** `git diff f827d6e e5c07c5` shows `images: []` changing to `images: [<new entry>]` — this is an append, not an overwrite. User likely saw `.squad/agents/` team roster (Artist, Butters, Critic, Curator, Kyle, Ralph, Scribe, Stan, Tolkien, Wendy) and conflated "agents" (squad team members) with "images" (gallery content). **Conclusion:** No data corruption. Frontend rendering correct. Room count shows "1 / 5 pieces" as expected for first publish. Hosted orchestrator append behavior matches documented contract in `docs/architecture/frontend-hosted-update-guide.md`. **Suggested fix:** None needed for code; recommend clarifying "squad agents" vs. "gallery images" in user communication.
