// Thin orchestrator. The actual daily work is performed by the Squad agents
// (see .squad/*.md) — this script exists so a Clawpilot automation has a single
// entry point to invoke. In practice the automation will run:
//
//   copilot --agent squad --yolo
//
// and Squad will read the .md files and drive the day. This script is here for
// (a) sanity-checking the repo state before/after, and (b) future use if we want
// to bypass copilot CLI for headless runs.

import { execSync } from "node:child_process";

console.log("== Pre-run gallery check ==");
execSync("node scripts/rebuild-routes.mjs", { stdio: "inherit" });

console.log("\n== Hand off to Squad ==");
console.log("Run the following to perform today's session:");
console.log("  copilot --agent squad --yolo");
console.log("\n(After completion, this script will validate and commit.)");
