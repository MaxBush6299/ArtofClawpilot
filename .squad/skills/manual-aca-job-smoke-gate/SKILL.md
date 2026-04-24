---
name: "manual-aca-job-smoke-gate"
description: "Prove a Container Apps Job is safe to promote by keeping it manual first, then using a smoke branch plus fixed run dates for durable publish/no-op/skip checks."
domain: "platform"
confidence: "high"
source: "earned"
---

## Context

Use this when a hosted workflow is almost ready for cutover but the scheduler should not be enabled until the real Azure job wiring is proven.

## Patterns

- Add an explicit job trigger mode so infra can stay `Manual` until smoke sign-off, then flip to `Schedule` at promotion time.
- Before counting smoke, confirm Azure actually contains the expected hosted surface: `Microsoft.App/jobs`, the ACA managed environment, the user-assigned managed identity, and the paired Log Analytics workspace for the same deployment.
- Expose a fixed `RUN_DATE_UTC` override so the same logical day can be replayed for hosted idempotency proof.
- Split smoke into two safety bands:
  - auth/wiring dry-run with no push
  - durable proof on a disposable branch with push enabled
- Keep the durable smoke branch separate from `main` so the real GitHub App write path is exercised without publishing production gallery state.
- Require the hosted log stream to show `already_resolved` and zero extra call counts on the rerun, not just “no second commit.”
- Require at least one non-fixture hosted proof of the real reasoning + image surfaces before promotion; a fixture-backed ACA run proves platform wiring, but not live model readiness.

## Anti-Patterns

- Do not enable the daily scheduler before the hosted branch proof passes.
- Do not treat a partial Azure deploy (for example, only SWA + Key Vault) as hosted readiness; the live gate starts only once the ACA Job stack exists.
- Do not try to prove idempotent reruns with dry-run alone; there is no durable ledger mutation to resolve against.
- Do not point hosted smoke commits at `main`.
