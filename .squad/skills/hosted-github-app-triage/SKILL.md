---
name: "hosted-github-app-triage"
description: "Diagnose hosted Azure Container Apps Job GitHub App authentication and permission failures, and enforce smoke-branch gates."
domain: "platform"
confidence: "high"
source: "earned"
---

## Context

Use this when an Azure Container Apps Job successfully runs the orchestrator and produces changes, but the bootstrap shell's git push fails with permission or authentication errors.

## Patterns

- **Separate authentication from authorization:** a `Permission denied` error on push usually means the GitHub App installation token was valid (clone succeeded) but the app lacks repository Contents: Write permission or branch protection blocks it.
- **Enforce the smoke-branch gate:** if the failure happens during Phase B/C hosted smoke proof and the job is configured to push to `main`, reject the proposal to fix permissions and rerun against `main`. The documented smoke contract in `hosted-smoke-checklist.md` and `manual-aca-job-smoke-gate` skill requires durable proof to run on a disposable `hosted-smoke` branch, never `main`.
- **Recovery path for smoke failures:**
  1. Create the `hosted-smoke` branch if it doesn't exist
  2. Verify GitHub App has Contents: Read & Write permissions in the repository settings
  3. Redeploy the ACA Job with `githubBranch=hosted-smoke`
  4. Rerun the smoke proof phases on the smoke branch
- **Check branch protection:** if the GitHub App has write permissions but push still fails, inspect branch protection rules. The app must either be explicitly allowed or protection must be disabled on the target branch during smoke.
- **ACA log fields to review:** `bootstrap` phase logs should include `git_push_failed` with `exitCode: 128` and redacted stderr showing `Permission to <owner>/<repo>.git denied`. Bootstrap emits `run_failed` with these fields for correlation in Log Analytics.

## When to Triage vs Approve

- **Triage required:** job pushed to `main` during smoke, or smoke phase logs show `git_push_failed` with permission errors
- **Approve fix:** GitHub App permissions were verified/corrected, job redeployed with `githubBranch=hosted-smoke`, and Phase B proof passed on the smoke branch
- **Reject shortcut:** do not approve fixing permissions and rerunning against `main` if the original smoke design required a disposable branch

## Example Recovery Sequence

```bash
# 1. Create smoke branch from main
git checkout main
git pull
git checkout -b hosted-smoke
git push origin hosted-smoke

# 2. Verify GitHub App permissions in repo Settings > Integrations > GitHub Apps
# - Contents: Read & Write (not just Read)
# - If branch protection exists on hosted-smoke, either disable it or whitelist the app

# 3. Redeploy ACA Job with updated branch parameter
# (Bicep parameter: githubBranch=hosted-smoke)

# 4. Manually start the job and verify Phase B proof logs show:
# - orchestrator: write_set_validated, commit_ready
# - bootstrap: push_completed
# - one commit on hosted-smoke branch

# 5. Rerun same job with same hostedRunDateOverride, confirm:
# - orchestrator: already_resolved
# - no second commit on hosted-smoke
```

## Why It Works

The smoke-branch gate protects production gallery state during proof. If permissions fail on `main`, it's a healthy enforcement — the fix is to honor the documented branch requirement, not bypass it. Once the smoke proof passes on the disposable branch, promotion to `main` with the scheduler enabled becomes the final cutover step.

## Verification After Permission Fix

After GitHub App permissions are corrected (Contents: Read & Write granted), verify the fix by checking:

1. **Manual job execution succeeds**: `az containerapp job start` returns execution ID, status transitions from Running → Succeeded
2. **Log Analytics shows complete flow**: Query `ContainerAppConsoleLogs_CL` for the execution and verify all expected events appear:
   - `bootstrap.run_started` → `auth.token_acquired` → `git.clone_completed`
   - `runner.command_started` → `orchestrator.run_started`
   - All role phases (curator, critic/skip, artist)
   - `validation.write_set_validated` → `git.commit_ready`
   - **Critical:** `git.push_completed` with no errors
3. **Commit lands on target branch**: Use `gh api repos/<owner>/<repo>/commits/<branch>` to verify the latest commit matches the execution timestamp and author (should be the bot name)
4. **No exit code 128 or permission errors**: Bootstrap logs should not contain `git_push_failed` event

## Success Indicators

A healthy push completion log looks like:
```json
{
  "phase": "git",
  "event": "push_completed",
  "changedPathCount": 3,
  "changedPaths": ["data/gallery.json", "data/next-brief.json", "public/gallery/..."],
  "timestamp": "...",
  "jobExecutionName": "..."
}
```

## Art of Clawpilot Example

- `docs/architecture/hosted-smoke-checklist.md`: Phase B requires `githubBranch=hosted-smoke`
- `.squad/skills/manual-aca-job-smoke-gate/SKILL.md`: Anti-pattern is "Do not point hosted smoke commits at `main`"
- `scripts/hosted-bootstrap.mjs`: emits structured `git_push_failed` logs with `exitCode` and redacted stderr
- **2026-04-27 successful resolution:** Execution artclaw-daily-job-2pewehrfleuls-j3e3a2s completed end-to-end on main after GitHub App granted Contents: Write. Log Analytics confirmed `push_completed` event, commit a57c085117e892e4042743994e9b68c3e8f03d84 landed on main. Duration: 79 seconds, no errors or retries.
