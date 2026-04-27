import { GUIDING_DESCRIPTION_MAX_CHARS, REQUEST_BODY_MAX_BYTES } from "./config.js";

const SAFE_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SAFE_CALLER_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export class RequestValidationError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

export function validateContentLength(request) {
  const rawLength = request.headers.get("content-length");
  if (!rawLength) {
    return;
  }
  const length = Number(rawLength);
  if (Number.isFinite(length) && length > REQUEST_BODY_MAX_BYTES) {
    throw new RequestValidationError("payload_too_large", "Request body must be 50KB or smaller.", {
      maxBytes: REQUEST_BODY_MAX_BYTES,
    });
  }
}

export async function parseGenerateRequest(request) {
  validateContentLength(request);
  let body;
  try {
    body = await request.json();
  } catch {
    throw new RequestValidationError("invalid_json", "Request body must be valid JSON.");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new RequestValidationError("body_invalid", "Request body must be a JSON object.");
  }

  const requestId = normalizeRequiredSafeString(body.requestId, "requestId", SAFE_ID_RE);
  const correlationId = normalizeOptionalSafeString(body.correlationId, "correlationId", SAFE_ID_RE) || requestId;
  const callerIdentity =
    normalizeOptionalSafeString(body.callerIdentity, "callerIdentity", SAFE_CALLER_RE) || "clawpilot-agent";
  const guidingDescription = normalizeGuidingDescription(body.guidingDescription);

  return {
    requestId,
    correlationId,
    callerIdentity,
    guidingDescription,
  };
}

function normalizeRequiredSafeString(value, fieldName, pattern) {
  if (typeof value !== "string" || !value.trim()) {
    throw new RequestValidationError(`${fieldName}_required`, `${fieldName} is required.`);
  }
  return normalizeSafeString(value, fieldName, pattern);
}

function normalizeOptionalSafeString(value, fieldName, pattern) {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new RequestValidationError(`${fieldName}_invalid`, `${fieldName} must be a string.`);
  }
  return normalizeSafeString(value, fieldName, pattern);
}

function normalizeSafeString(value, fieldName, pattern) {
  const trimmed = value.trim();
  if (!pattern.test(trimmed)) {
    throw new RequestValidationError(
      `${fieldName}_invalid`,
      `${fieldName} must start with an alphanumeric character and contain only safe identifier characters.`,
    );
  }
  return trimmed;
}

function normalizeGuidingDescription(value) {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new RequestValidationError("guidingDescription_invalid", "guidingDescription must be a string.");
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  if (trimmed.length > GUIDING_DESCRIPTION_MAX_CHARS) {
    throw new RequestValidationError(
      "guidingDescription_too_long",
      `guidingDescription must be ${GUIDING_DESCRIPTION_MAX_CHARS} characters or fewer.`,
      { maxChars: GUIDING_DESCRIPTION_MAX_CHARS },
    );
  }
  return trimmed;
}
