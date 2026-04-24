import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const pythonCommand = process.platform === "win32" ? "python" : "python3";

const result = spawnSync(
  pythonCommand,
  ["-m", "orchestrator.main", "--repo-root", REPO_ROOT, ...process.argv.slice(2)],
  {
    cwd: REPO_ROOT,
    stdio: "inherit",
    env: process.env,
  }
);

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}
