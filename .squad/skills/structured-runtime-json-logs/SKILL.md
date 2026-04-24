---
name: "structured-runtime-json-logs"
description: "Emit Azure-friendly JSONL diagnostics for hosted orchestrator phases and failure attribution."
domain: "observability"
confidence: "high"
source: "earned"
---

## Context
Use this when a hosted workflow needs operator-friendly logs in Azure Container Apps Jobs or Log Analytics.

## Patterns
- Emit one JSON log line per significant event with stable top-level fields like `timestamp`, `level`, `phase`, `event`, `runDate`, and `traceId`.
- Treat `validation`, `git`, and `image_generation` as explicit phases instead of burying them under generic runtime text.
- Log both failure classification (`skip` vs `hard_fail`) and the final run failure envelope so operators can see intent and exit behavior.
- Keep call-count and reviewed-prompt proof logs in the same stream so hosted troubleshooting does not depend on replaying model calls.

## Anti-Patterns
- Do not rely on plain-text phase banners that are hard to query in Log Analytics.
- Do not collapse image-generation failures into a generic `artist` error when operators need a precise phase.
