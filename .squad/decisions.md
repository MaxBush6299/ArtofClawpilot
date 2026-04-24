# Decisions

## 2026-04-24

- The squad roster uses South Park character names for project agents; Scribe and Ralph keep their fixed names.
- Art of Clawpilot is treated as an AI-powered art gallery with a daily execution that produces exactly one new image or one structured skip record.
- The hosted target stack is React/Vite on the frontend with Python orchestration/runtime on Azure, using Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, and Azure Static Web Apps.
- The hosted daily run uses one Azure Container Apps Job shell with a user-assigned managed identity, Key Vault-backed secrets, and a GitHub App path that posts directly to `main`; Microsoft-specific implementation choices stay grounded in Microsoft Learn.
- The model split is fixed: `grok-4-20-reasoning` handles reasoning work and `MAI-Image-2e` handles final image generation.
- The backlog execution order is stable: `#2 -> #3/#4/#5/#12 -> #7/#8/#9/#11 -> #6 -> #10/#13 -> #14/#15`, and no wholesale backlog expansion is needed before execution.
- Issue #6 is the Python orchestrator integration issue; `node scripts/hosted-bootstrap.mjs` stays as the platform-owned checkout/push shell while hosted runtime executes `python -m orchestrator.main`.
- Runtime contracts are explicit: Curator, Critic, and Artist run in-process, roles return data while the orchestrator owns persistence, `data/gallery.json` is the canonical ledger including durable `skipped` entries, and the Artist path is bounded to exactly three reasoning calls plus one final image-generation call.
- Validation and review rules are fixed: malformed Curator/Critic/Artist output becomes a structured day-closing contract failure when repo/auth surfaces are healthy, while pre-run corruption, auth failure, and git failure remain hard-fail boundaries.
- Butters' closure gate for issue #6 required one durable publish-or-skip outcome per `runDate`, idempotent rerun no-op behavior, phase-tagged failures, write-set safety, explicit final call-count observability, and proof that only the reviewed prompt package reaches `MAI-Image-2e`.
- The first execution wave was the hosted foundation slice (#3, #4, #5, #12); README cutover remained a follow-through item, not a blocker to foundation execution.
- Current handoff status: the hosted runner foundation is in place; issues #2, #3, #4, #5, #6, #7, and #12 are closed; issues #8, #9, #10, #11, #13, #14, and #15 remain open. Exact orchestration detail for the final #6 closeout was not present in the squad logs reviewed by Scribe.
