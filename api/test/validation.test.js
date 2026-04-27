import assert from "node:assert/strict";
import { GUIDING_DESCRIPTION_MAX_CHARS } from "../src/lib/config.js";
import { parseGenerateRequest, RequestValidationError } from "../src/lib/validation.js";

function request(body, headers = {}) {
  const normalizedHeaders = new Map(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), String(value)]),
  );
  return {
    headers: {
      get(name) {
        return normalizedHeaders.get(name.toLowerCase());
      },
    },
    async json() {
      return body;
    },
  };
}

async function assertValidationError(body, expectedCode) {
  await assert.rejects(
    () => parseGenerateRequest(request(body)),
    (error) => error instanceof RequestValidationError && error.code === expectedCode,
  );
}

const minimal = await parseGenerateRequest(request({ requestId: "req-abc123" }));
assert.deepEqual(minimal, {
  requestId: "req-abc123",
  correlationId: "req-abc123",
  callerIdentity: "clawpilot-agent",
  guidingDescription: undefined,
});

const guidingDescription = "  Follow the morning light, but keep room choice with Curator.  ";
const withGuidance = await parseGenerateRequest(
  request({
    requestId: "req-guided",
    correlationId: "corr-guided",
    callerIdentity: "clawpilot-agent",
    guidingDescription,
  }),
);
assert.equal(withGuidance.guidingDescription, guidingDescription.trim());

const maxGuidance = "x".repeat(GUIDING_DESCRIPTION_MAX_CHARS);
const acceptedMax = await parseGenerateRequest(request({ requestId: "req-max", guidingDescription: maxGuidance }));
assert.equal(acceptedMax.guidingDescription.length, GUIDING_DESCRIPTION_MAX_CHARS);

await assertValidationError({}, "requestId_required");
await assertValidationError({ requestId: "has spaces" }, "requestId_invalid");
await assertValidationError({ requestId: "req-too-long-" + "x".repeat(130) }, "requestId_invalid");
await assertValidationError({ requestId: "req-bad-guidance", guidingDescription: 123 }, "guidingDescription_invalid");
await assertValidationError(
  { requestId: "req-long-guidance", guidingDescription: "x".repeat(GUIDING_DESCRIPTION_MAX_CHARS + 1) },
  "guidingDescription_too_long",
);

console.log("PASS validation.test.js");
