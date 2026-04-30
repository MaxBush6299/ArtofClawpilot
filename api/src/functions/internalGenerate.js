import { app } from "@azure/functions";
import { createInternalGenerateHandler } from "../lib/internalGenerateHandler.js";

export const internalGenerate = createInternalGenerateHandler();

app.http("internalGenerate", {
  route: "internal/generate",
  methods: ["POST"],
  authLevel: "anonymous",
  handler: internalGenerate,
});
