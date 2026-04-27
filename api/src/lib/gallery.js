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
