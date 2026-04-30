import assert from "node:assert/strict";
import { createInternalGenerateHandler } from "../src/lib/internalGenerateHandler.js";

function request(body) {
  return {
    headers: {
      get(name) {
        return name.toLowerCase() === "x-clawpilot-key" ? "test-key" : undefined;
      },
    },
    async json() {
      return body;
    },
  };
}

function context() {
  const logs = [];
  const log = (message, fields) => logs.push({ level: "info", message, fields });
  log.warn = (message, fields) => logs.push({ level: "warn", message, fields });
  log.error = (message, fields) => logs.push({ level: "error", message, fields });
  return { log, logs };
}

let starts = 0;
const duplicateHandler = createInternalGenerateHandler({
  validateApiKey: async () => true,
  findExistingManualOutcomeByRequestId: async (requestId) => ({
    available: true,
    outcome: "publish",
    runDate: "2026-04-27",
    runId: `manual-2026-04-27-${requestId}`,
  }),
  utcRunDate: () => {
    throw new Error("today_run_id_was_derived");
  },
  startManualGenerationJob: async () => {
    starts += 1;
    return { id: "should-not-start", name: "should-not-start" };
  },
});

const duplicate = await duplicateHandler(request({ requestId: "same-request" }), context());
assert.equal(duplicate.status, 200);
assert.equal(duplicate.jsonBody.status, "already_resolved");
assert.equal(duplicate.jsonBody.runDate, "2026-04-27");
assert.equal(duplicate.jsonBody.runId, "manual-2026-04-27-same-request");
assert.equal(starts, 0);

const acceptedHandler = createInternalGenerateHandler({
  validateApiKey: async () => true,
  findExistingManualOutcomeByRequestId: async () => ({ available: true }),
  findExistingOutcome: async () => ({ available: true }),
  utcRunDate: () => "2026-04-30",
  startManualGenerationJob: async ({ runDate, runId, requestId }) => {
    starts += 1;
    assert.equal(runDate, "2026-04-30");
    assert.equal(runId, "manual-2026-04-30-fresh-request");
    assert.equal(requestId, "fresh-request");
    return { id: "execution-id", name: "execution-name" };
  },
});

const accepted = await acceptedHandler(request({ requestId: "fresh-request" }), context());
assert.equal(accepted.status, 202);
assert.equal(accepted.jsonBody.status, "accepted");
assert.equal(accepted.jsonBody.runId, "manual-2026-04-30-fresh-request");
assert.equal(starts, 1);

console.log("PASS internalGenerate.test.js");
