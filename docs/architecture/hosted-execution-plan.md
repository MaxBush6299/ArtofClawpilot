# Hosted execution plan

> Status: execution-ready plan for the hosted daily-run backlog.

This plan assumes the architecture in [`hosted-daily-run.md`](./hosted-daily-run.md) stays authoritative and that Microsoft-specific implementation choices continue to cite Microsoft Learn during delivery.

## Preserved decisions

- Hosted target: one Python orchestrator running in Azure Container Apps Jobs.
- Hosted reasoning model: `grok-4-20-reasoning`.
- Hosted image model: `MAI-Image-2e`.
- Automation GitHub App pushes directly to `main`.

## Sequence and dependencies

| Phase | Issues | Lead | Depends on | Exit bar |
| --- | --- | --- | --- | --- |
| 0. Contract locked | #2 | Stan | — | Hosted architecture + execution contract remain the source of truth. |
| 1. Hosted foundation | #3, #4, #5, #12 | Tolkien | #2 | Azure job shell, managed identity, GitHub write path, and container packaging are deployable. |
| 2. Runtime contracts | #7, #8, #9, #11 | Kyle | #2 | Role I/O, bounded `grok-4-20-reasoning` flow, reviewed prompt package, and validation contract are concrete. |
| 3. Orchestrator integration | #6 | Kyle | #3, #4, #5, #7, #8, #9, #11, #12 | One Python entrypoint executes the day end to end with deterministic outcomes. |
| 4. Hardening | #10, #13 | Kyle | #6, #11 | Skip handling and observability cover the real hosted flow. |
| 5. Cutover proof | #14, #15 | Butters | #6, #10, #13 | Docs, dry-run checks, and the manual-first hosted smoke proof in `hosted-smoke-checklist.md` support production cutover. |

## Parallel team lanes

| Team member | Immediate lane | Parallel handoffs |
| --- | --- | --- |
| Stan | Keep #2 authoritative, sharpen backlog, review contracts and phase exits. | Final review on #6 and cutover bar on #15. |
| Tolkien | Deliver #3/#4/#5/#12 together as one hosted platform slice. | Hand container/job/auth contracts to Kyle as soon as env shape is stable. |
| Kyle | Start #7 first, then split into #8, #9, and #11 in parallel. | Pull Tolkien's runtime/env contract into #6 once platform shape is ready. |
| Butters | Co-author #11 validation expectations while Kyle defines contracts. | Own #15, review #6/#10/#13, and block cutover until dry-run + hosted smoke pass. |
| Wendy | Validate frontend assumptions against the new `data/*.json` and `public/gallery/*` contract. | If contract changes affect rendering or docs, pick up #14 follow-through without blocking backend work. |

## Validation start gates

Butters's acceptance bar for #11 and #15 now lives in [`hosted-validation-gates.md`](./hosted-validation-gates.md). Kyle can start runtime-contract implementation immediately against that tester-owned matrix, while Wendy's frontend compatibility check continues in parallel and becomes a cutover gate rather than a backend start blocker.

## Implementation notes that should stay explicit

1. Artist is a bounded flow: `grok-4-20-reasoning` call 1 analyzes inputs, call 2 drafts the prompt package, call 3 reviews/finalizes it, then one `MAI-Image-2e` generation call executes.
2. Validation is shared infrastructure, not a last-minute test-only layer: preflight, post-run, asset-path, malformed-model-output, and one-outcome-per-day checks all live under #11 and are reused by #6 and #15.
3. Per Microsoft Learn, deployment names are runtime config and hosted auth should use managed identity / Microsoft Entra ID rather than stored API keys; the hosted env should carry separate reasoning and MAI endpoints so the two API surfaces stay explicit.
4. The hosted platform shell remains the GitHub App bootstrap, but its default hosted command must be the Python orchestrator (`python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE"`) so #6 runs through the containerized path by default.

## Ready / blockers

No backlog blocker remains after sharpening. The team is ready to execute in the sequence above.

## Current hosted-test status

As of the #15 platform/ops slice, the repo now defines a manual-first ACA Job smoke procedure and the infra knobs needed to keep the job off-schedule until that proof passes. The production scheduler remains blocked on the evidence and sign-off recorded in [`hosted-smoke-checklist.md`](./hosted-smoke-checklist.md).
