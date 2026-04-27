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

## 2026-04-27

- First Azure Container Apps Job invocation succeeded through MAI image generation but failed at `git push` with `Permission to MaxBush6299/ArtofClawpilot.git denied ... exitCode 128`. Root cause: GitHub App installation lacks Contents: Read & Write permission. Clone succeeded (proving Contents: Read exists); push failed (proving Contents: Write missing).
- Team consensus on recovery: Fix GitHub App permissions by granting Contents: Read & Write, then rerun smoke proof on disposable `hosted-smoke` branch per documented safety stance (docs/architecture/hosted-smoke-checklist.md). Do not rerun against main until smoke proof passes on branch.
- Hosted smoke architecture requires three phases on disposable `hosted-smoke` branch: Phase A (auth/wiring dry-run), Phase B (durable publish + idempotent rerun), Phase C (failure-path proof). No smoke commits land on main during proof. Butters reviews ACA logs + smoke branch commits before sign-off.
- Architecture decision reaffirmed: direct push to `main` is the correct design (not PR-based). Single-transaction publish contract (one commit per `runDate`) preserves design intent and one-commit-per-day invariant. PR-based fallback deferred unless branch protection explicitly blocks app.
- Documentation gap: Add GitHub App permission prerequisites to docs/architecture/hosted-daily-run.md as setup requirement section, explicitly listing Contents: Read & Write as required for git push to main and Metadata: Read-only as automatically included.
- Smoke proof checkpoint: After Phase B proof passes on hosted-smoke branch with idempotent rerun validation, production cutover resumes with intended direct-push-to-main design. Permissions fix and branch policy form the immediate safe next step.
- Frontend guide decision: Wendy drafted `docs/architecture/frontend-hosted-update-guide.md` with preliminary sign-off identifying zero code changes needed for Home.tsx and Room.tsx. Frontend already defensively handles `skipped[]` at top level and optional audit fields; both pages use optional chaining and truthy checks.
- Frontend guide review (rejected): Butters identified five inaccuracies requiring Stan revision: (1) `runDate` overstated as full ISO 8601 instead of `YYYY-MM-DD` day key; (2) Room.tsx criticism rendering misdescribed as optional chaining vs. actual `{img.criticism && (...)}`; (3) static JSON import overclaimed as TypeScript build-time schema validation; (4) Home cover incorrectly assumed to be newest image despite pre-existing images; (5) contract boundaries conflated data validation with frontend tolerance.
- Frontend guide decision (approved): Stan revised `docs/architecture/frontend-hosted-update-guide.md` with all corrections verified against Home.tsx actual behavior, Room.tsx rendering, orchestrator append semantics, and hosted contract specs. Butters approved after verification. Approval scope: frontend-guide accuracy for smoke practicality and `skipped[]` tolerance; does not supersede broader hosted smoke gates in `hosted-smoke-checklist.md`.
