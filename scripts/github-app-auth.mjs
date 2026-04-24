import { createSign } from "node:crypto";

const GITHUB_API_VERSION = "2022-11-28";

function base64UrlEncode(value) {
  const buffer = Buffer.isBuffer(value)
    ? value
    : Buffer.from(typeof value === "string" ? value : JSON.stringify(value));
  return buffer.toString("base64url");
}

function createGitHubAppJwt({ appId, privateKey }) {
  const now = Math.floor(Date.now() / 1000);
  const signingInput = [
    base64UrlEncode({ alg: "RS256", typ: "JWT" }),
    base64UrlEncode({
      iat: now - 60,
      exp: now + 9 * 60,
      iss: appId,
    }),
  ].join(".");

  const signer = createSign("RSA-SHA256");
  signer.update(signingInput);
  signer.end();

  return `${signingInput}.${signer.sign(privateKey).toString("base64url")}`;
}

export function getRequiredEnv(name) {
  const value = process.env[name];
  if (!value || !value.trim()) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getGitHubRepoUrl({ owner, repo }) {
  return `https://github.com/${owner}/${repo}.git`;
}

export async function getGitHubInstallationToken({ appId, installationId, privateKey }) {
  const jwt = createGitHubAppJwt({ appId, privateKey });
  const response = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${jwt}`,
        "User-Agent": "art-of-clawpilot-hosted-runner",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
      },
    }
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `Failed to mint GitHub installation token (${response.status} ${response.statusText}): ${body}`
    );
  }

  const json = await response.json();
  return {
    token: json.token,
    expiresAt: json.expires_at,
  };
}
