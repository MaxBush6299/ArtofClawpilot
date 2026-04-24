---
name: "contract-negative-probes"
description: "Probe LLM and image integration contracts with malformed-but-valid payloads to catch untyped failures."
domain: "testing"
confidence: "high"
source: "observed"
tools:
  - name: "powershell"
    description: "Runs quick Python repro scripts against local adapters."
    when: "You need to prove a contract failure escapes as a raw exception instead of a typed error."
---

## Context
Use this when a role or client claims typed contract validation for model outputs or API responses. Happy-path dry runs can pass while malformed-but-valid payloads still crash the runtime with raw exceptions.

## Patterns
- Feed each role adapter JSON that is syntactically valid but missing one required field.
- Verify the failure becomes the promised typed contract error rather than `KeyError`, `ValueError`, or decode exceptions.
- For image clients, probe both missing payload shapes and invalid base64 bodies on otherwise successful HTTP responses.
- Seed whatever precondition is required to reach the target path; if the live fixture repo has no prior image, drive `CriticRole` with a synthetic latest image instead of assuming an end-to-end dry run will hit Critic.
- Treat negative probes as acceptance gates whenever docs require phase-clear or typed failure handling.

## Examples
- `orchestrator/roles/curator.py` currently indexes `payload["targetRoomId"]`; a malformed JSON object can raise raw `KeyError`.
- `orchestrator/contracts.py` and `orchestrator/validation.py` define typed failure codes, so adapter code should normalize bad payloads into those contracts.
- `orchestrator/integrations/foundry.py` should convert malformed image response bodies into `response_shape_invalid` instead of letting decode errors escape.

## Anti-Patterns
- Assuming JSON parse success means contract validation is complete.
- Validating only happy-path fixture flows before approving model-integration issues.
- Letting transport adapters leak raw parser or decoder exceptions across the runtime boundary.
