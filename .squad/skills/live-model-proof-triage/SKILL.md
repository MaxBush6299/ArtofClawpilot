---
name: "live-model-proof-triage"
description: "Run a safe live-model proof for Art of Clawpilot and separate hosted-boundary blockers from model-surface failures."
domain: "runtime"
confidence: "medium"
source: "earned"
---

## Context
Use this when someone wants a real model-backed Art of Clawpilot proof before the hosted Azure job is fully proven.

## Patterns
- First audit Azure for the hosted boundary: confirm the resource group actually has the Container Apps managed environment, ACA Job, user-assigned identity, and Log Analytics workspace expected by `hosted-smoke-checklist.md`.
- If hosted resources are missing, do not push ad hoc durable gallery changes from the main checkout. Use a disposable repo snapshot under `workspace\` for runtime probing.
- For local live proof, mint `AZURE_ACCESS_TOKEN` from `az account get-access-token --resource https://cognitiveservices.azure.com`, set separate reasoning and image endpoint/deployment env vars, and run `python -m orchestrator.main` against the disposable repo with a fixed future `--run-date`.
- On failure before persistence, verify `git status --short` and `git diff --name-only` stay empty so the hard-fail path proves zero write-set behavior.
- If reasoning succeeds but publish fails, hit the MAI endpoint directly with the same token and deployment to distinguish an orchestration bug from a model/runtime outage.

## Anti-Patterns
- Do not test a live proof in the dirty main checkout.
- Do not call the hosted path “ready” just because Foundry deployments exist; the ACA Job boundary and GitHub App wiring must also exist.
- Do not treat a hard-fail image-generation run as a structured skip; if persistence never starts, the expected write set is no files changed.
