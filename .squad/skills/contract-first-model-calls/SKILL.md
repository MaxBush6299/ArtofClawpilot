---
name: "contract-first-model-calls"
description: "Build bounded model workflows that parse every step into typed contracts before downstream side effects."
domain: "error-handling"
confidence: "high"
source: "earned"
tools:
  - name: "python"
    description: "Implements shared parsing helpers, bounded call flows, and dry-run fixtures."
    when: "When a hosted workflow depends on structured model output and explicit failure taxonomy."
---

## Context
Use this pattern when a workflow chains multiple model calls and later side effects must depend only on validated structured output.

## Patterns
- Parse each model response immediately into typed fields; never index raw JSON directly in business logic.
- Attach explicit reason codes for malformed output, call-budget overflow, auth, deployment, content-filter, and response-shape failures.
- Bound multistep reasoning flows with a fixed stage order and exact call ceiling.
- Require downstream image or publish steps to accept only the final reviewed package, not draft text.
- Add deterministic fixture scenarios that prove publish, structured skip, and hard-fail classifications.

## Examples
- `orchestrator/roles/parsing.py`
- `orchestrator/roles/artist.py`
- `orchestrator/integrations/foundry.py`
- `orchestrator/main.py`

## Anti-Patterns
- Letting missing model fields surface as `KeyError` or `TypeError`.
- Reopening prompt design inside the image client.
- Treating auth or wrong-deployment failures as structured skips.
