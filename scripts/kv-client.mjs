// Resolves Foundry endpoint + deployment from Azure Key Vault using DefaultAzureCredential.
// Locally: uses your `az login`. In the daily SWA build / managed-identity context: uses MI.
import { DefaultAzureCredential } from "@azure/identity";
import { SecretClient } from "@azure/keyvault-secrets";

const VAULT_URL = process.env.KEY_VAULT_URL; // e.g. https://kv-artofclawpilot.vault.azure.net

export async function getFoundryConfig() {
  if (!VAULT_URL) {
    // Fallback for local dev with explicit env vars
    if (process.env.FOUNDRY_ENDPOINT && process.env.FOUNDRY_DEPLOYMENT) {
      return {
        endpoint: process.env.FOUNDRY_ENDPOINT,
        deployment: process.env.FOUNDRY_DEPLOYMENT,
      };
    }
    throw new Error(
      "KEY_VAULT_URL not set, and no FOUNDRY_ENDPOINT/FOUNDRY_DEPLOYMENT fallback in env."
    );
  }
  const credential = new DefaultAzureCredential();
  const client = new SecretClient(VAULT_URL, credential);
  const [endpoint, deployment] = await Promise.all([
    client.getSecret("foundry-endpoint"),
    client.getSecret("foundry-deployment-name"),
  ]);
  return { endpoint: endpoint.value, deployment: deployment.value };
}

export function getCredential() {
  return new DefaultAzureCredential();
}
