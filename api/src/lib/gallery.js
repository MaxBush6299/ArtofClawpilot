import { getGalleryUrl } from "./config.js";

function logWarn(context, message, fields) {
  if (typeof context.warn === "function") {
    context.warn(message, fields);
  } else if (typeof context.log?.warn === "function") {
    context.log.warn(message, fields);
  } else if (typeof context.log === "function") {
    context.log(message, fields);
  }
}

export async function findExistingOutcome(runId, context) {
  const galleryUrl = getGalleryUrl();
  try {
    const response = await fetch(galleryUrl, {
      headers: { accept: "application/json" },
    });
    if (!response.ok) {
      logWarn(context, "gallery precheck unavailable", {
        status: response.status,
      });
      return { available: false };
    }
    const gallery = await response.json();
    for (const skip of gallery.skipped || []) {
      if (skip.runId === runId) {
        return { available: true, outcome: "skip" };
      }
    }
    for (const room of gallery.rooms || []) {
      for (const image of room.images || []) {
        if ((image.runId || image.id) === runId) {
          return { available: true, outcome: "publish" };
        }
      }
    }
    return { available: true };
  } catch (error) {
    logWarn(context, "gallery precheck failed", {
      errorType: error?.name,
      message: error?.message,
    });
    return { available: false };
  }
}

export async function findExistingManualOutcomeByRequestId(requestId, context) {
  const galleryUrl = getGalleryUrl();
  try {
    const response = await fetch(galleryUrl, {
      headers: { accept: "application/json" },
    });
    if (!response.ok) {
      logWarn(context, "gallery precheck unavailable", {
        status: response.status,
      });
      return { available: false };
    }
    const gallery = await response.json();
    for (const skip of gallery.skipped || []) {
      if (!isManualApiRecord(skip)) {
        continue;
      }
      const match = parseManualRunIdForRequest(skip.runId, requestId);
      if (match) {
        return { available: true, outcome: "skip", ...match };
      }
    }
    for (const room of gallery.rooms || []) {
      for (const image of room.images || []) {
        if (!isManualApiRecord(image)) {
          continue;
        }
        const match = parseManualRunIdForRequest(image.runId, requestId);
        if (match) {
          return { available: true, outcome: "publish", ...match };
        }
      }
    }
    return { available: true };
  } catch (error) {
    logWarn(context, "gallery precheck failed", {
      errorType: error?.name,
      message: error?.message,
    });
    return { available: false };
  }
}

function isManualApiRecord(record) {
  return record?.triggerSource === "manual-api";
}

function parseManualRunIdForRequest(runId, requestId) {
  if (typeof runId !== "string" || typeof requestId !== "string") {
    return undefined;
  }
  const prefix = "manual-";
  if (!runId.startsWith(prefix)) {
    return undefined;
  }
  const runDate = runId.slice(prefix.length, prefix.length + 10);
  const separator = runId[prefix.length + 10];
  const suffix = runId.slice(prefix.length + 11);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(runDate) || separator !== "-" || suffix !== requestId) {
    return undefined;
  }
  return { runDate, runId };
}
