import { ContainerAppsAPIClient } from "@azure/arm-appcontainers";
import { credential, getContainerJobConfig } from "./config.js";

const JOB_OVERRIDE_NAMES = new Set([
  "RUN_DATE_UTC",
  "RUN_ID",
  "TRIGGER_SOURCE",
  "REQUEST_ID",
  "CALLER_IDENTITY",
  "CORRELATION_ID",
  "HOSTED_TRACE_ID",
  "GUIDING_DESCRIPTION",
]);

export async function startManualGenerationJob({
  runDate,
  runId,
  requestId,
  callerIdentity,
  correlationId,
  guidingDescription,
}) {
  const { subscriptionId, resourceGroup, jobName, containerName } = getContainerJobConfig();
  const client = new ContainerAppsAPIClient(credential, subscriptionId);
  const job = await client.jobs.get(resourceGroup, jobName);
  const template = buildExecutionTemplate(job.template, containerName, {
    RUN_DATE_UTC: runDate,
    RUN_ID: runId,
    TRIGGER_SOURCE: "manual-api",
    REQUEST_ID: requestId,
    CALLER_IDENTITY: callerIdentity,
    CORRELATION_ID: correlationId,
    HOSTED_TRACE_ID: correlationId,
    GUIDING_DESCRIPTION: guidingDescription,
  });

  return client.jobs.beginStartAndWait(resourceGroup, jobName, { template });
}

function buildExecutionTemplate(jobTemplate, targetContainerName, overrides) {
  const containers = (jobTemplate?.containers || []).map((container, index) => {
    if (container.name !== targetContainerName && !(index === 0 && !targetContainerName)) {
      return cloneContainer(container);
    }
    return withEnvOverrides(container, overrides);
  });
  if (containers.length === 0) {
    throw new Error("Container Apps Job template has no containers to execute.");
  }
  if (!containers.some((container) => container.name === targetContainerName) && targetContainerName) {
    containers[0] = withEnvOverrides(containers[0], overrides);
  }
  return {
    containers,
    initContainers: jobTemplate?.initContainers?.map(cloneContainer),
  };
}

function cloneContainer(container) {
  return {
    ...container,
    command: container.command ? [...container.command] : undefined,
    args: container.args ? [...container.args] : undefined,
    env: container.env ? container.env.map((entry) => ({ ...entry })) : undefined,
    resources: container.resources ? { ...container.resources } : undefined,
  };
}

function withEnvOverrides(container, overrides) {
  const merged = cloneContainer(container);
  const env = (merged.env || [])
    .filter((entry) => entry.name && !JOB_OVERRIDE_NAMES.has(entry.name))
    .map((entry) => ({ ...entry }));
  for (const [name, value] of Object.entries(overrides)) {
    if (value !== undefined && value !== null && value !== "") {
      env.push({ name, value });
    }
  }
  merged.env = env;
  return merged;
}
