---
name: "github-app-permission-triage"
description: "Diagnose GitHub App permission failures when git operations partially succeed but write operations fail."
domain: "platform"
confidence: "high"
source: "earned"
---

## Context

Use this pattern when a GitHub App-authenticated workflow succeeds at clone/read but fails at push/write with "Permission denied" or HTTP 403/404 errors.

## Patterns

- If `git clone` succeeds but `git push` fails with "Permission denied" or "exitCode 128", the GitHub App installation likely lacks **Contents: Read & write** repository permissions.
- If the error message is "Resource not accessible by integration" (HTTP 403), the app has the permission in settings but the repository installation has not accepted the updated scope.
- When the GitHub App can mint an installation token (no auth error during token acquisition) but write operations fail, the permission scope—not the credentials—is the blocker.
- Distinguish between:
  - **Missing permission in app settings:** the app definition never granted the scope
  - **Outdated installation:** the app settings were updated but the repository installation was not refreshed
  - **Branch protection blocking the app:** the app has write permissions but branch rules reject the push (different error: "protected branch hook declined")
- GitHub App permissions are **not retroactive**. Updating app permissions requires the installation to accept the new scope before the token will carry the expanded grant.

## Diagnostic steps

1. Confirm the GitHub App can mint a token (check bootstrap logs for `token_acquired`).
2. Confirm `git clone` succeeds (repo read access works).
3. If `git push` fails with "Permission denied", check the GitHub App's **Repository permissions → Contents** setting.
4. If the setting shows "Read & write" but push still fails, navigate to the repository's GitHub App installation settings and verify the new scope has been accepted.
5. If both settings are correct, check branch protection rules for direct-push restrictions on the target branch.

## Resolution

- Add or update **Contents** to **Read & write** in the GitHub App settings.
- Navigate to the repository installation settings and accept the updated permissions.
- Retry the push operation.

## Documentation requirement

When designing automation that uses a GitHub App for git push, explicitly document the required repository permissions in the setup prerequisites, not just in troubleshooting sections.

## Art of Clawpilot example

- `scripts/hosted-bootstrap.mjs` (git push command at line 426)
- `docs/architecture/hosted-daily-run.md` (should include GitHub App permission prerequisites)
- Azure Container Apps Job diagnostic pattern: bootstrap succeeds through clone, orchestrator succeeds through image generation, but git push fails with permission error
