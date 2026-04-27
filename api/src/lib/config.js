import { DefaultAzureCredential } from "@azure/identity";

export const GUIDING_DESCRIPTION_MAX_CHARS = 1000;
export const REQUEST_BODY_MAX_BYTES = 50 * 1024;
export const API_KEY_SECRET_NAME = process.env.CLAWPILOT_API_KEY_SECRET_NAME || "clawpilot-api-key";

export const credential = new DefaultAzureCredential();

export function getRequiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable ${name}`);
  }
  return value;
}

export function getKeyVaultUrl() {
  return process.env.KEY_VAULT_URL?.trim() || process.env.CLAWPILOT_KEY_VAULT_URL?.trim();
}

export function getContainerJobConfig() {
  return {
    subscriptionId: getRequiredEnv("AZURE_SUBSCRIPTION_ID"),
    resourceGroup:
      process.env.CONTAINER_APP_JOB_RESOURCE_GROUP?.trim() ||
      process.env.ACA_JOB_RESOURCE_GROUP?.trim() ||
      getRequiredEnv("AZURE_RESOURCE_GROUP"),
    jobName:
      process.env.CONTAINER_APP_JOB_NAME?.trim() ||
      process.env.ACA_JOB_NAME?.trim() ||
      getRequiredEnv("HOSTED_JOB_NAME"),
    containerName: process.env.CONTAINER_APP_JOB_CONTAINER_NAME?.trim() || "runner",
  };
}

export function getGalleryUrl() {
  const explicitUrl = process.env.CLAWPILOT_GALLERY_STATE_URL?.trim();
  if (explicitUrl) {
    return explicitUrl;
  }
  const owner = process.env.GITHUB_OWNER?.trim() || "MaxBush6299";
  const repo = process.env.GITHUB_REPO?.trim() || "ArtofClawpilot";
  const branch = process.env.GITHUB_BRANCH?.trim() || "main";
  return `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/data/gallery.json`;
}
