# History - Kyle

## Seed Context

- Requested by Max Bush.
- Project: Art of Clawpilot, an AI-powered virtual art gallery that adds one new piece each day.
- Stack: React + Vite frontend, Python orchestration/runtime, Azure Container Apps Jobs, Azure Key Vault, Microsoft Foundry, Azure Static Web Apps.
- Current issue focus: #2, the hosted daily-run architecture and execution contract.

## Learnings

- Kyle owns Python orchestration, Foundry integration, and persisted runtime contracts.
- 2026-04-24 runtime-contract slice started in `orchestrator/` with typed role contracts, reusable validation, a bounded three-step Artist flow, and preflight state loading/validation scaffolding for issues #7, #8, #9, and #11.
- 2026-04-24 Microsoft Learn grounding for this slice: reasoning uses deployment-name config on the Azure OpenAI chat completions endpoint with Entra/managed-identity auth, while MAI-Image-2e uses the MAI image generation endpoint and enforces the documented 768px-min / 1,048,576-max-pixel size bounds.
- 2026-04-24 issue #8/#9 follow-through tightened role parsing in `orchestrator/roles/*.py` so Curator, Critic, and each Artist stage machine-validate model output immediately and turn missing/malformed fields into typed contract failures instead of uncaught KeyErrors.
- 2026-04-24 the hosted runtime now logs normalized reasoning usage metadata plus MAI image metadata in `orchestrator/main.py`, and `orchestrator/integrations/foundry.py` requires a `final-reviewed` prompt package before the single MAI call.
- 2026-04-24 reusable pattern: keep model-response parsing in a shared helper (`orchestrator/roles/parsing.py`) and map budget/auth/deployment/content-filter/response-shape outcomes distinctly so dry-run fixtures can prove skip-vs-hard-fail behavior without desktop dependencies.
- 2026-04-24 closure pass for #10/#11: `orchestrator/validation.py` is now the shared pre-run + post-run contract surface, including idempotency resolution and exact write-set checks for publish vs skip outcomes.
- 2026-04-24 structured skip records in `orchestrator/contracts.py` now carry nested `error` metadata plus optional `creativeContext`; `orchestrator/main.py` populates room/brief/reviewed-prompt context on artist-stage generation failures so `data/gallery.json` stays reviewable after a skipped day.
- 2026-04-24 validation evidence used fixture-driven commands through `python -m orchestrator.main` plus `npm run build`; disposable repos under `workspace\\kyle-closure-10-11-*` proved persisted skip/no-op behavior and malformed Critic output handling without touching the main gallery state.
- 2026-04-24 issue #13 follow-through: `orchestrator/main.py` now emits JSONL phase/event diagnostics with `runDate` and `traceId` context, plus explicit `validation`, `git`, and `image_generation` records so ACA Job logs can distinguish publish, skip, and hard-fail paths without desktop tooling.
- 2026-04-24 issue #15 proof slice: `npm run orchestrator:proof` now clones disposable repos under `workspace/issue-15-proof`, seeds Critic-path fixtures, proves dry-run leaves no extra diff behind, and covers publish/skip/malformed-output/budget/no-op/pre-run-hard-fail scenarios through `python -m orchestrator.main`.
- 2026-04-24 live proof attempt against Azure resource `eval-t1` confirmed the runtime split is correct: reasoning succeeded on `https://eval-t1.cognitiveservices.azure.com` with deployment `grok-4-20-reasoning`, but MAI image generation at `https://eval-t1.services.ai.azure.com` with deployment `MAI-Image-2e-1` returned HTTP 500 before persistence, leaving a disposable proof repo with an empty write set.
