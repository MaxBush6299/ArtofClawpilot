import assert from "node:assert/strict";
import { findExistingOutcome } from "../src/lib/gallery.js";

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
        { id: "image-2", runId: "manual-2026-04-27-req-1", runDate: "2026-04-27" },
      ],
    },
  ],
  skipped: [{ id: "skip-manual-2026-04-27-req-skip", runId: "manual-2026-04-27-req-skip" }],
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
assert.deepEqual(await findExistingOutcome("manual-2026-04-27-new", context()), { available: true });

installFetch({}, false, 503);
assert.deepEqual(await findExistingOutcome("manual-2026-04-27-new", context()), { available: false });

console.log("PASS gallery.test.js");
