import { validateApiKey } from "./auth.js";
import { findExistingManualOutcomeByRequestId, findExistingOutcome } from "./gallery.js";
import { parseGenerateRequest, RequestValidationError } from "./validation.js";

function utcRunDate() {
  return new Date().toISOString().slice(0, 10);
}

function json(status, body) {
  return {
    status,
    jsonBody: body,
    headers: {
      "cache-control": "no-store",
    },
  };
}

async function startManualGenerationJobDefault(args) {
  const { startManualGenerationJob } = await import("./jobs.js");
  return startManualGenerationJob(args);
}

function logWarn(context, message, fields) {
  if (typeof context.warn === "function") {
    context.warn(message, fields);
  } else if (typeof context.log?.warn === "function") {
    context.log.warn(message, fields);
  } else if (typeof context.log === "function") {
    context.log(message, fields);
  }
}

function logError(context, message, fields) {
  if (typeof context.error === "function") {
    context.error(message, fields);
  } else if (typeof context.log?.error === "function") {
    context.log.error(message, fields);
  } else if (typeof context.log === "function") {
    context.log(message, fields);
  }
}

export function createInternalGenerateHandler(dependencies = {}) {
  const authorize = dependencies.validateApiKey || validateApiKey;
  const findDuplicateManualOutcome =
    dependencies.findExistingManualOutcomeByRequestId || findExistingManualOutcomeByRequestId;
  const findOutcome = dependencies.findExistingOutcome || findExistingOutcome;
  const startJob = dependencies.startManualGenerationJob || startManualGenerationJobDefault;
  const getRunDate = dependencies.utcRunDate || utcRunDate;

  return async function internalGenerateHandler(request, context) {
    let payload;
    try {
      const authorized = await authorize(request);
      if (!authorized) {
        logWarn(context, "manual generation rejected: unauthorized");
        return json(401, {
          status: "unauthorized",
          error: { code: "unauthorized", message: "Missing or invalid X-Clawpilot-Key." },
        });
      }

      payload = await parseGenerateRequest(request);

      const duplicate = await findDuplicateManualOutcome(payload.requestId, context);
      if (duplicate.outcome) {
        return json(200, {
          status: "already_resolved",
          outcome: duplicate.outcome,
          requestId: payload.requestId,
          correlationId: payload.correlationId,
          runDate: duplicate.runDate,
          runId: duplicate.runId,
        });
      }

      const runDate = getRunDate();
      const runId = `manual-${runDate}-${payload.requestId}`;

      context.log("manual generation request accepted for validation", {
        requestId: payload.requestId,
        correlationId: payload.correlationId,
        callerIdentity: payload.callerIdentity,
        runDate,
        runId,
        hasGuidingDescription: Boolean(payload.guidingDescription),
        guidingDescriptionChars: payload.guidingDescription?.length || 0,
      });

      const existing = await findOutcome(runId, context);
      if (existing.outcome) {
        return json(200, {
          status: "already_resolved",
          outcome: existing.outcome,
          requestId: payload.requestId,
          correlationId: payload.correlationId,
          runDate,
          runId,
        });
      }

      const execution = await startJob({
        runDate,
        runId,
        requestId: payload.requestId,
        callerIdentity: payload.callerIdentity,
        correlationId: payload.correlationId,
        guidingDescription: payload.guidingDescription,
      });

      return json(202, {
        status: "accepted",
        requestId: payload.requestId,
        correlationId: payload.correlationId,
        runDate,
        runId,
        executionId: execution.id,
        executionName: execution.name,
        duplicatePrecheck: existing.available ? "not_found" : "unavailable",
      });
    } catch (error) {
      if (error instanceof RequestValidationError) {
        return json(400, {
          status: "validation_error",
          error: { code: error.code, message: error.message, details: error.details },
        });
      }
      logError(context, "manual generation trigger failed", {
        requestId: payload?.requestId,
        correlationId: payload?.correlationId,
        errorType: error?.name,
        message: error?.message,
      });
      return json(503, {
        status: "trigger_failed",
        error: {
          code: "container_job_start_failed",
          message: "Manual generation could not be started.",
        },
      });
    }
  };
}
