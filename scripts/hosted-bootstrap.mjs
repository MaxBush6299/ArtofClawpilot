import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  getGitHubInstallationToken,
  getGitHubRepoUrl,
  getRequiredEnv,
} from "./github-app-auth.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const DEFAULT_HOSTED_RUNNER_COMMAND =
  'python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --run-id "$RUN_ID"';
const LOG_COMPONENT = "hosted-bootstrap";
const LOG_RUNTIME_CONTEXT = {
  component: LOG_COMPONENT,
  runtime: "aca-job",
};

for (const [envName, fieldName] of [
  ["HOSTED_JOB_NAME", "jobName"],
  ["CONTAINER_APP_JOB_NAME", "jobName"],
  ["CONTAINER_APP_JOB_EXECUTION_NAME", "jobExecutionName"],
  ["CONTAINER_APP_REPLICA_NAME", "replicaName"],
]) {
  const envValue = process.env[envName]?.trim();
  if (envValue && !(fieldName in LOG_RUNTIME_CONTEXT)) {
    LOG_RUNTIME_CONTEXT[fieldName] = envValue;
  }
}

function printHelp() {
  console.log(`Hosted bootstrap contract:

Required environment variables
  GITHUB_APP_ID
  GITHUB_APP_INSTALLATION_ID
  GITHUB_APP_PRIVATE_KEY
  GITHUB_OWNER
  GITHUB_REPO

Optional environment variables
  GITHUB_BRANCH            default: main
  GIT_AUTHOR_NAME          default: Art of Clawpilot Bot
  GIT_AUTHOR_EMAIL         default: artofclawpilot-bot@users.noreply.github.com
  HOSTED_WORKDIR           default: workspace
  HOSTED_RUNNER_COMMAND    default: python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --run-id "$RUN_ID"
  HOSTED_PUSH_CHANGES      default: false
  HOSTED_COMMIT_MESSAGE    default: chore: hosted runner update for <UTC date>
  RUN_DATE_UTC             default: current UTC date; pin this for smoke/idempotency replay
  RUN_ID                   default: scheduled-{RUN_DATE_UTC}; use for manual or concurrent runs

Injected at runtime
  REPO_WORKSPACE           fresh clone path used by the hosted command
  RUN_DATE_UTC             UTC date for this hosted run
  RUN_ID                   unique run identifier for idempotency
  HOSTED_TRACE_ID          shared correlation id forwarded into the Python runner

Usage
  node scripts/hosted-bootstrap.mjs
  node scripts/hosted-bootstrap.mjs --help
`);
}

function isTruthy(value) {
  return ["1", "true", "yes", "on"].includes((value ?? "").toLowerCase());
}

function setLogContext(fields = {}) {
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== "") {
      LOG_RUNTIME_CONTEXT[key] = value;
    }
  }
}

function redactText(value, redactions = []) {
  let safeValue = value;
  for (const redaction of redactions) {
    if (redaction) {
      safeValue = safeValue.split(redaction).join("***");
    }
  }
  return safeValue;
}

function summarizeText(value, { maxLines = 20, maxChars = 4000 } = {}) {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const lines = trimmed.split(/\r?\n/);
  const limitedLines = lines.slice(-maxLines);
  let summary = limitedLines.join("\n");
  if (summary.length > maxChars) {
    summary = summary.slice(summary.length - maxChars);
  }
  return summary;
}

function createBootstrapError({
  phase,
  code,
  message,
  exitCode,
  command,
  stdout,
  stderr,
  details,
  errorType,
  retryable,
}) {
  const error = new Error(message);
  error.phase = phase;
  error.code = code;
  error.exitCode = exitCode;
  error.command = command;
  error.stdout = stdout;
  error.stderr = stderr;
  error.details = details;
  error.errorType = errorType;
  error.retryable = retryable;
  return error;
}

function normalizeBootstrapError(error, overrides = {}) {
  return createBootstrapError({
    phase: overrides.phase ?? error?.phase ?? "bootstrap",
    code: overrides.code ?? error?.code ?? "bootstrap_failed",
    message: overrides.message ?? error?.message ?? "Hosted bootstrap failed.",
    exitCode: overrides.exitCode ?? error?.exitCode,
    command: overrides.command ?? error?.command,
    stdout: overrides.stdout ?? error?.stdout,
    stderr: overrides.stderr ?? error?.stderr,
    details: overrides.details ?? error?.details,
    errorType: overrides.errorType ?? error?.errorType ?? error?.name,
    retryable: overrides.retryable ?? error?.retryable,
  });
}

async function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const commandLine = options.shell ? command : [command, ...args].join(" ");
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: options.capture || options.mirrorOutput ? ["ignore", "pipe", "pipe"] : "inherit",
      shell: options.shell ?? false,
    });

    let stdout = "";
    let stderr = "";

    if (options.capture || options.mirrorOutput) {
      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
        if (options.mirrorOutput) {
          process.stdout.write(chunk);
        }
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
        if (options.mirrorOutput) {
          process.stderr.write(chunk);
        }
      });
    }

    child.on("error", (error) => {
      reject(
        createBootstrapError({
          phase: options.phase ?? "bootstrap",
          code: options.spawnCode ?? `${options.failureCode ?? "command_failed"}_spawn`,
          message: `Failed to start ${options.label ?? commandLine}: ${error.message}`,
          command: commandLine,
          errorType: error.name,
          retryable: false,
        }),
      );
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }

      const safeStdout = summarizeText(redactText(stdout, options.redactions));
      const safeStderr = summarizeText(redactText(stderr, options.redactions));
      reject(
        createBootstrapError({
          phase: options.phase ?? "bootstrap",
          code: options.failureCode ?? "command_failed",
          message: `${options.label ?? commandLine} exited with code ${code}.`,
          exitCode: code,
          command: commandLine,
          stdout: safeStdout,
          stderr: safeStderr,
          retryable: false,
        }),
      );
    });
  });
}

async function runGit(args, options = {}) {
  return run("git", ["--no-pager", ...args], {
    ...options,
    label: options.label ?? `git ${args.join(" ")}`,
  });
}

async function runPhase(phase, code, action) {
  try {
    return await action();
  } catch (error) {
    throw normalizeBootstrapError(error, { phase, code });
  }
}

function emitLog(level, phase, event, fields = {}) {
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    ...LOG_RUNTIME_CONTEXT,
    phase,
    event,
    ...fields,
  };
  const line = JSON.stringify(payload);
  if (level === "ERROR") {
    console.error(line);
    return;
  }
  console.log(line);
}

async function main() {
  if (process.argv.includes("--help")) {
    printHelp();
    return;
  }

  const runDate = process.env.RUN_DATE_UTC?.trim() || new Date().toISOString().slice(0, 10);
  const runId = process.env.RUN_ID?.trim() || `scheduled-${runDate}`;
  const traceId = process.env.HOSTED_TRACE_ID?.trim() || `hosted-${runId}`;
  setLogContext({
    runDate,
    runId,
    traceId,
  });
  const {
    owner,
    repo,
    branch,
    appId,
    installationId,
    privateKey,
    authorName,
    authorEmail,
    workdir,
    clonePath,
    runnerCommand,
    pushChanges,
    commitMessage,
  } = await runPhase("config", "config_invalid", async () => ({
    owner: getRequiredEnv("GITHUB_OWNER"),
    repo: getRequiredEnv("GITHUB_REPO"),
    branch: process.env.GITHUB_BRANCH?.trim() || "main",
    appId: getRequiredEnv("GITHUB_APP_ID"),
    installationId: getRequiredEnv("GITHUB_APP_INSTALLATION_ID"),
    privateKey: getRequiredEnv("GITHUB_APP_PRIVATE_KEY"),
    authorName: process.env.GIT_AUTHOR_NAME?.trim() || "Art of Clawpilot Bot",
    authorEmail:
      process.env.GIT_AUTHOR_EMAIL?.trim() || "artofclawpilot-bot@users.noreply.github.com",
    workdir: path.join(REPO_ROOT, process.env.HOSTED_WORKDIR?.trim() || "workspace"),
    clonePath: path.join(
      path.join(REPO_ROOT, process.env.HOSTED_WORKDIR?.trim() || "workspace"),
      "repo",
    ),
    runnerCommand:
      process.env.HOSTED_RUNNER_COMMAND?.trim() || DEFAULT_HOSTED_RUNNER_COMMAND,
    pushChanges: isTruthy(process.env.HOSTED_PUSH_CHANGES),
    commitMessage:
      process.env.HOSTED_COMMIT_MESSAGE?.trim() ||
      `chore: hosted runner update for ${runDate}`,
  }));
  setLogContext({
    repo: `${owner}/${repo}`,
    branch,
  });

  emitLog("INFO", "bootstrap", "run_started", {
    pushChanges,
    runnerCommand,
    workdir,
  });

  const { token, expiresAt } = await runPhase("auth", "github_app_auth_failed", () =>
    getGitHubInstallationToken({
      appId,
      installationId,
      privateKey,
    }),
  );

  const cleanRepoUrl = getGitHubRepoUrl({ owner, repo });
  const authenticatedRepoUrl = `https://x-access-token:${token}@github.com/${owner}/${repo}.git`;

  emitLog("INFO", "auth", "token_acquired", {
    tokenExpiresAt: expiresAt,
  });

  await runPhase("workspace", "workspace_prepare_failed", async () => {
    await fs.rm(workdir, { recursive: true, force: true });
    await fs.mkdir(workdir, { recursive: true });
  });
  emitLog("INFO", "workspace", "workspace_prepared", {
    workdir,
    clonePath,
  });

  emitLog("INFO", "git", "clone_started", {
    clonePath,
  });
  await runPhase("git", "git_clone_failed", async () => {
    await runGit(["clone", "--branch", branch, "--single-branch", authenticatedRepoUrl, clonePath], {
      capture: true,
      phase: "git",
      failureCode: "git_clone_failed",
      redactions: [token, authenticatedRepoUrl],
    });
    await runGit(["remote", "set-url", "origin", cleanRepoUrl], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_remote_config_failed",
    });
    await runGit(["config", "user.name", authorName], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_author_config_failed",
    });
    await runGit(["config", "user.email", authorEmail], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_author_config_failed",
    });
  });
  emitLog("INFO", "git", "clone_completed", {
    clonePath,
  });

  emitLog("INFO", "runner", "command_started", {
    command: runnerCommand,
    repoWorkspace: clonePath,
  });
  await runPhase("runner", "runner_command_failed", () =>
    run(runnerCommand, [], {
      cwd: clonePath,
      env: {
        ...process.env,
        REPO_WORKSPACE: clonePath,
        RUN_DATE_UTC: runDate,
        RUN_ID: runId,
        HOSTED_TRACE_ID: traceId,
      },
      shell: true,
      mirrorOutput: true,
      phase: "runner",
      failureCode: "runner_command_failed",
      label: "hosted runner command",
    }),
  );
  emitLog("INFO", "runner", "command_completed", {
    command: runnerCommand,
  });

  const status = await runPhase("git", "git_status_failed", () =>
    runGit(["status", "--porcelain"], {
      cwd: clonePath,
      capture: true,
      phase: "git",
      failureCode: "git_status_failed",
    }),
  );
  const hasChanges = status.stdout.trim().length > 0;
  const changedPaths = status.stdout
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => line.slice(3))
    .map((line) => (line.includes(" -> ") ? line.split(" -> ")[1] : line));

  if (!hasChanges) {
    emitLog("INFO", "git", "workspace_clean", {
      changedPathCount: 0,
    });
    return;
  }

  if (!pushChanges) {
    emitLog("WARNING", "git", "push_skipped", {
      reason: "HOSTED_PUSH_CHANGES is false",
      changedPathCount: changedPaths.length,
      changedPaths,
    });
    return;
  }

  emitLog("INFO", "git", "commit_started", {
    changedPathCount: changedPaths.length,
    changedPaths,
    commitMessage,
  });
  await runPhase("git", "git_push_failed", async () => {
    await runGit(["add", "--all"], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_add_failed",
    });
    await runGit(["commit", "-m", commitMessage], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_commit_failed",
    });
    await runGit(["push", authenticatedRepoUrl, `HEAD:${branch}`], {
      capture: true,
      cwd: clonePath,
      phase: "git",
      failureCode: "git_push_failed",
      redactions: [token, authenticatedRepoUrl],
    });
  });
  emitLog("INFO", "git", "push_completed", {
    changedPathCount: changedPaths.length,
    changedPaths,
  });
}

main().catch((error) => {
  const failure = normalizeBootstrapError(error);
  const phase = failure.phase ?? "bootstrap";
  emitLog("ERROR", phase, "run_failed", {
    message: failure.message,
    errorCode: failure.code,
    errorType: failure.errorType,
    exitCode: failure.exitCode,
    command: failure.command,
    retryable: failure.retryable,
    stdout: failure.stdout,
    stderr: failure.stderr,
    details: failure.details,
  });
  process.exit(1);
});
