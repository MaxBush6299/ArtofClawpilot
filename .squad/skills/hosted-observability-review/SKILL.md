---
name: "hosted-observability-review"
description: "Review the hosted runner's JSON log contract across bootstrap and orchestrator phases without requiring a live Azure job."
domain: "testing"
confidence: "high"
source: "earned"
tools:
  - name: "powershell"
    description: "Runs fixture-backed orchestrator scenarios and bootstrap failure probes."
    when: "Use when validating phase coverage, failure attribution, and log shape before hosted smoke."
---

## Context
Use this pattern when reviewing hosted diagnostics work for Art of Clawpilot. The goal is to prove that operators can understand where a run failed from raw ACA console logs, while keeping the real Azure smoke proof deferred until cutover testing.

## Patterns
- Exercise the orchestrator with fixture-backed publish, structured-skip, hard-fail, and already-resolved no-op runs so every major outcome emits its JSON log sequence.
- Use a throwaway repo under `workspace\` for one non-dry fixture publish plus rerun when you need proof of `write_set_validated`, `git` readiness logs, and the zero-call idempotent no-op path without touching the main checkout.
- Seed a repo root with at least one prior image when you need to hit the Critic path; an empty gallery will skip Critic entirely.
- Probe the hosted bootstrap with intentionally bad GitHub App inputs to verify its `run_started` / `run_failed` JSON contract without needing real credentials.
- Check that logs cover preflight, role execution, image generation, validation, and git/bootstrap phases, and that failures name both the phase and the reason.
- Compare bootstrap and orchestrator payloads for shared correlation fields; if one side lacks the promised `traceId` (or equivalent), flag it as a Log Analytics usability gap even if both sides are already JSON.

## Examples
- `python -m orchestrator.main --dry-run --repo-root <fixture repo> --run-date 2099-02-09 --fixture-scenario publish`
- `python -m orchestrator.main --repo-root workspace\\review-hosted-logs --run-date 2099-02-10 --use-fixtures --fixture-scenario publish` followed by the same command again to prove `already_resolved`
- `python -m orchestrator.main --dry-run --repo-root <fixture repo> --run-date 2099-02-06 --fixture-scenario malformed-critic`
- `python -m orchestrator.main --dry-run --run-date 2099-02-07 --fixture-scenario image-auth-failure`
- `node scripts/hosted-bootstrap.mjs` with dummy GitHub App inputs to verify structured auth failure logging

## Anti-Patterns
- Do not approve observability work from code inspection alone when quick fixture probes can show the real emitted log shape.
- Do not assume an empty-gallery dry run proves Critic coverage.
- Do not treat “JSON logs exist” as sufficient if bootstrap and orchestrator cannot be correlated cleanly in Log Analytics.
