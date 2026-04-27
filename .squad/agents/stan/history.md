# History - Stan

## Seed Context

- Requested by Max Bush.
- Project: Art of Clawpilot, an AI-powered virtual art gallery that adds one new piece each day.
- Stack: React + Vite frontend, Python orchestration/runtime, Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, Azure Static Web Apps.
- Current issue focus: #2, the hosted daily-run architecture and execution contract.

## Learnings

- Team initialized on 2026-04-24 with South Park cast names.
- 2026-04-24 backlog review: issue #2 is the gating contract; recommended flow is architecture first, then platform/auth foundation, then runner implementation, then validation/observability/docs/tests.
- 2026-04-24 backlog review update: final order is #2 (Stan), then #3/#4/#5/#12, then #6/#7/#8/#9/#10/#11/#13, then #14/#15; dependency chain is #2 -> #3/#4/#5/#12 -> #7/#8/#9/#11 -> #6 -> #10/#13 -> #14/#15.
- 2026-04-24 issue #2 draft landed at `docs/architecture/hosted-daily-run.md`; it recommends one Python orchestrator in Azure Container Apps Job, with Curator/Critic/Artist as in-process role steps and a day-scoped idempotency contract.
- 2026-04-24 issue #2 draft recommends GitHub App-based git push to `main` for the publish transaction and a user-assigned managed identity on the job for Key Vault and Foundry auth.
- 2026-04-24 issue #2 kickoff recorded: `docs/architecture/hosted-daily-run.md` is linked from `README.md`; no blocking clarification is needed, and the only open assumption is whether the automation GitHub App can push directly to `main`.
- 2026-04-24 clarification update: Microsoft-specific implementation guidance for the hosted daily run now explicitly cites Microsoft Learn, including UTC cron behavior for Container Apps Jobs and Bicep support for scheduled jobs with user-assigned managed identity.
- 2026-04-24 model split update: hosted reasoning is standardized on the deployed `grok-4-20-reasoning` model, while hosted image generation stays on `MAI-Image-2e`.
- 2026-04-24 clarification closeout: issue #2 no longer has blocking clarification work; the hosted daily-run doc now grounds Microsoft choices in Microsoft Learn and keeps the `grok-4-20-reasoning`/`MAI-Image-2e` split explicit.
- 2026-04-24 issue detail review: the backlog is mostly executable after #2, but #6 should be rewritten to match the Python orchestrator target and #7/#8/#9/#11/#15 should make the Artist handoff explicit as a bounded three-call `grok-4-20-reasoning` flow (analyze -> prompt draft -> prompt review) before the final `MAI-Image-2e` call.
- 2026-04-24 issue detail review closeout: do not spread backlog detail wholesale right now; only refine #6 for the Python orchestrator target plus #7/#8/#9/#11/#15 for explicit Artist I/O, bounded reasoning flow, reviewed prompt handoff, and validation/tests around call bounds and malformed reasoning outputs.
- 2026-04-24 execution sharpening pass: issue titles/bodies for #6/#7/#8/#9/#11/#15 are the concrete execution contract, with #6 as Python orchestrator integration after #7/#8/#9/#11 land.
- 2026-04-24 execution sharpening pass: `docs/architecture/hosted-execution-plan.md` is the concise team sequence doc; the delivery order stays #2 -> #3/#4/#5/#12 -> #7/#8/#9/#11 -> #6 -> #10/#13 -> #14/#15, and no blocker remains.
- 2026-04-24 execution readiness closeout: first execution wave is #3/#4/#5/#12; Tolkien owns foundation, Kyle owns runtime contracts and orchestrator, Butters owns validation/cutover, Wendy owns frontend and data-contract follow-through, and Stan reviews phase exits.
- 2026-04-24 remaining-work review: GitHub issue status is lagging the repo state. Close #8 and #9 immediately after recording approval/landed code, then run a closure pass on #10/#11 against `orchestrator/main.py`, `orchestrator/validation.py`, `orchestrator/integrations/foundry.py`, and `orchestrator/roles/artist.py` before treating #13, #15, and final #14 docs as the cutover sequence.
- 2026-04-24 #13 revision: `scripts/hosted-bootstrap.mjs` must be a first-class observability peer to `orchestrator/main.py`, carrying the same `runDate`, `traceId`, and ACA execution metadata while forwarding `HOSTED_TRACE_ID` into the Python runner.
- 2026-04-24 #13 revision: bootstrap failure logs need structured triage fields (`errorCode`, `exitCode`, `command`, redacted stdout/stderr excerpts) so auth/git/bootstrap failures are queryable in ACA Job + Log Analytics without changing the one-image-or-one-skip runtime contract.
- 2026-04-24 hosted deployment triage: Max deployed all resources but git push failed with "Permission denied... exitCode 128". GHCP investigation confirmed the clone succeeded, MAI generation worked, but the GitHub App likely lacks Contents: Read & Write permissions. The team's architecture already contemplated branch protection blocking the app, but the immediate blocker is repository permissions, not branch rules. The correct path is to update the GitHub App permissions to include Contents: Read & Write, verify the installation accepts the new scope, then rerun the job. No architecture change is needed; the permission surface was an assumption in the original design that was not explicitly documented as a GitHub App setup prerequisite.
- 2026-04-27 team triage synthesis: Stan synthesized findings from Tolkien, Kyle, and Butters. Root cause confirmed as GitHub App permissions boundary. Documentation gap identified: add GitHub App permission prerequisites (Contents: Read & Write for git push to main) to `docs/architecture/hosted-daily-run.md` as setup requirement, not troubleshooting note. Direct push to main remains primary design. Approved recovery path: create disposable `hosted-smoke` branch, fix permissions, redeploy job with `githubBranch=hosted-smoke`, rerun Phase B proof on branch. After smoke proof passes, production cutover resumes with intended direct-push-to-main design.
