import crypto from "node:crypto";
import { SecretClient } from "@azure/keyvault-secrets";
import { API_KEY_SECRET_NAME, credential, getKeyVaultUrl } from "./config.js";

let cachedSecret;
let cachedAt = 0;
const CACHE_TTL_MS = 60_000;

function timingSafeEqualString(left, right) {
  const leftBuffer = Buffer.from(left, "utf8");
  const rightBuffer = Buffer.from(right, "utf8");
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

async function getExpectedApiKey() {
  const now = Date.now();
  if (cachedSecret && now - cachedAt < CACHE_TTL_MS) {
    return cachedSecret;
  }
  const keyVaultUrl = getKeyVaultUrl();
  if (!keyVaultUrl) {
    throw new Error("Missing KEY_VAULT_URL or CLAWPILOT_KEY_VAULT_URL");
  }
  const client = new SecretClient(keyVaultUrl, credential);
  const secret = await client.getSecret(API_KEY_SECRET_NAME);
  if (!secret.value) {
    throw new Error(`Key Vault secret ${API_KEY_SECRET_NAME} is empty`);
  }
  cachedSecret = secret.value;
  cachedAt = now;
  return cachedSecret;
}

export async function validateApiKey(request) {
  const provided = request.headers.get("x-clawpilot-key")?.trim();
  if (!provided) {
    return false;
  }
  const expected = await getExpectedApiKey();
  return timingSafeEqualString(provided, expected);
}
