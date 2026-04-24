# Skill: ACA Job Diagnostics

## When to use

Use this pattern when a hosted workflow runs inside Azure Container Apps Jobs and operators need reliable failure attribution in Log Analytics.

## Pattern

1. Emit **one JSON object per log line** to stdout/stderr from every hosted boundary (`bootstrap`, runtime, publish path).
2. Keep a shared minimum field set:
   - `component`
   - `phase`
   - `event`
   - `runDate`
   - `traceId`
3. Log explicit phase transitions and failure classification, not just exception text.
4. Distinguish:
   - role/runtime failures (`curator`, `critic`, `artist`, `publish`)
   - platform/bootstrap failures (`auth`, `workspace`, `git`, `runner`)
5. Document the matching KQL/operator path against `ContainerAppConsoleLogs_CL`, with `ContainerAppSystemLogs_CL` as the companion view for platform/runtime issues.
6. When a bootstrap shell launches the real runtime, have bootstrap inject the shared `traceId` into that child process and mirror ACA execution metadata (`jobName`, `jobExecutionName`, `replicaName`) so one query can stitch together both halves of the same run.
7. For bootstrap/process failures, emit machine-usable fields like `errorCode`, `exitCode`, `command`, and redacted stdout/stderr excerpts instead of only a free-form message.

## Why it works

- Azure Container Apps captures stdout/stderr directly, so JSONL survives the job boundary cleanly.
- Stable `phase` and `event` fields make KQL filters much easier than parsing free-form strings.
- Shared correlation fields let operators stitch together bootstrap, orchestrator, and retry behavior for a single UTC run date.

## Minimal operator query

```kusto
ContainerAppConsoleLogs_CL
| where ContainerGroupName_s startswith "<job-execution-name>"
| project TimeGenerated, ContainerName_s, Log_s
| order by TimeGenerated asc
```

## Art of Clawpilot example

- `scripts/hosted-bootstrap.mjs`
- `orchestrator/main.py`
- `docs/architecture/hosted-daily-run.md`
