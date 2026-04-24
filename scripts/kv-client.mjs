// Resolves Foundry endpoint + deployment from Azure Key Vault using DefaultAzureCredential.
// Locally: uses your `az login`. In the daily SWA build / managed-identity context: uses MI.
import { DefaultAzureCredential } from "@azure/identity";
import { SecretClient } from "@azure/keyvault-secrets";

const VAULT_URL = process.env.KEY_VAULT_URL; // e.g. https://kv-artofclawpilot.vault.azure.net

async function getSecretValue(client, ...names) {
  let lastError;
  for (const name of names) {
    try {
      const secret = await client.getSecret(name);
      if (secret?.value) return secret.value;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError ?? new Error(`Unable to resolve any of these secrets: ${names.join(", ")}`);
}

export async function getFoundryConfig() {
  if (!VAULT_URL) {
    // Fallback for local dev with explicit env vars
    if (
      (process.env.FOUNDRY_IMAGE_ENDPOINT || process.env.FOUNDRY_ENDPOINT) &&
      (process.env.FOUNDRY_IMAGE_DEPLOYMENT || process.env.FOUNDRY_DEPLOYMENT)
    ) {
      return {
        endpoint: process.env.FOUNDRY_IMAGE_ENDPOINT || process.env.FOUNDRY_ENDPOINT,
        deployment: process.env.FOUNDRY_IMAGE_DEPLOYMENT || process.env.FOUNDRY_DEPLOYMENT,
      };
    }
    throw new Error(
      "KEY_VAULT_URL not set, and no FOUNDRY_IMAGE_ENDPOINT/FOUNDRY_IMAGE_DEPLOYMENT fallback in env."
    );
  }
  const credential = new DefaultAzureCredential();
  const client = new SecretClient(VAULT_URL, credential);
  const [endpoint, deployment] = await Promise.all([
    getSecretValue(client, "foundry-image-endpoint", "foundry-endpoint"),
    getSecretValue(client, "foundry-image-deployment-name", "foundry-deployment-name"),
  ]);
  return { endpoint, deployment };
}

export function getCredential() {
  return new DefaultAzureCredential();
}
