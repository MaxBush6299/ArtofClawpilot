---
name: "foundry-runtime-surfaces"
description: "How Art of Clawpilot wires hosted Foundry reasoning and MAI image generation safely."
domain: "platform"
confidence: "high"
source: "earned"
---

## Context
Use this when touching hosted Foundry auth, endpoint wiring, Container Apps job env, or MAI image generation calls. The repo uses two different Microsoft inference surfaces and treats confusing them as a platform bug.

## Patterns
- Keep reasoning and image endpoints separate in config: reasoning uses the Azure OpenAI chat-completions endpoint, image generation uses the MAI endpoint on `services.ai.azure.com`.
- Treat deployment names as injected runtime config, not hard-coded model names.
- Keep auth surface explicit per endpoint: reasoning uses the Azure OpenAI bearer flow, while the MAI project endpoint may require a different Entra audience than the chat endpoint.
- Do not assume the MAI project endpoint accepts an omitted image API version; keep image API version explicit in runtime config and append it to the request URL.
- Classify Foundry failures early into auth, deployment-or-endpoint, content-filter, and malformed-response buckets so orchestrator policy can decide hard-fail vs skip cleanly.
- Preserve compatibility fallbacks only as secondary paths; the hosted contract should use explicit `FOUNDRY_REASONING_*` and `FOUNDRY_IMAGE_*` settings.
- For local live-model proof outside ACA, use an `az account get-access-token` fallback so the same integration code can be exercised without a managed identity endpoint.

## Examples
- `infra/main.bicep` injects `FOUNDRY_REASONING_ENDPOINT`, `FOUNDRY_REASONING_DEPLOYMENT`, `FOUNDRY_REASONING_API_VERSION`, `FOUNDRY_IMAGE_ENDPOINT`, and `FOUNDRY_IMAGE_DEPLOYMENT`.
- `orchestrator/integrations/foundry.py` posts reasoning to `/openai/deployments/{deployment}/chat/completions?...` and MAI image generation to `/mai/v1/images/generations?api-version=...`.
- `scripts/kv-client.mjs` prefers image-specific Key Vault secrets before falling back to legacy aliases.

## Anti-Patterns
- Do not reuse one generic endpoint for both reasoning and MAI.
- Do not fall back to API keys for hosted execution.
- Do not collapse content-filter or malformed-response cases into a generic API error when downstream orchestration needs the distinction.
