import assert from "node:assert/strict";
import { findExistingManualOutcomeByRequestId, findExistingOutcome } from "../src/lib/gallery.js";

function context() {
  const warnings = [];
  return {
    warnings,
    log: {
      warn(message, fields) {
        warnings.push({ message, fields });
      },
    },
  };
}

function installFetch(body, ok = true, status = 200) {
  globalThis.fetch = async () => ({
    ok,
    status,
    async json() {
      return body;
    },
  });
}

installFetch({
  rooms: [
    {
      images: [
        { id: "legacy-2026-04-27", runDate: "2026-04-27" },
        {
          id: "image-2",
          runId: "manual-2026-04-27-req-1",
          runDate: "2026-04-27",
          triggerSource: "manual-api",
        },
        {
          id: "manual-2026-04-27-non-manual-source",
          runId: "manual-2026-04-27-non-manual-source",
          runDate: "2026-04-27",
          triggerSource: "scheduled",
        },
        { id: "scheduled-image", runId: "scheduled-2026-04-27", runDate: "2026-04-27" },
      ],
    },
  ],
  skipped: [
    {
      id: "skip-manual-2026-04-27-req-skip",
      runId: "manual-2026-04-27-req-skip",
      triggerSource: "manual-api",
    },
    { id: "scheduled-skip", runId: "scheduled-2026-04-28", runDate: "2026-04-28" },
  ],
});

assert.deepEqual(await findExistingOutcome("manual-2026-04-27-req-1", context()), {
  available: true,
  outcome: "publish",
});
assert.deepEqual(await findExistingOutcome("legacy-2026-04-27", context()), {
  available: true,
  outcome: "publish",
});
assert.deepEqual(await findExistingOutcome("manual-2026-04-27-req-skip", context()), {
  available: true,
  outcome: "skip",
});
assert.deepEqual(await findExistingOutcome("scheduled-2026-04-27", context()), {
  available: true,
  outcome: "publish",
});
assert.deepEqual(await findExistingOutcome("manual-2026-04-27-new", context()), { available: true });
assert.deepEqual(await findExistingManualOutcomeByRequestId("req-1", context()), {
  available: true,
  outcome: "publish",
  runDate: "2026-04-27",
  runId: "manual-2026-04-27-req-1",
});
assert.deepEqual(await findExistingManualOutcomeByRequestId("req-skip", context()), {
  available: true,
  outcome: "skip",
  runDate: "2026-04-27",
  runId: "manual-2026-04-27-req-skip",
});
assert.deepEqual(await findExistingManualOutcomeByRequestId("2026-04-27", context()), { available: true });
assert.deepEqual(await findExistingManualOutcomeByRequestId("non-manual-source", context()), { available: true });
assert.deepEqual(await findExistingManualOutcomeByRequestId("fresh-req", context()), { available: true });

installFetch({}, false, 503);
assert.deepEqual(await findExistingOutcome("manual-2026-04-27-new", context()), { available: false });
assert.deepEqual(await findExistingManualOutcomeByRequestId("req-1", context()), { available: false });

console.log("PASS gallery.test.js");
