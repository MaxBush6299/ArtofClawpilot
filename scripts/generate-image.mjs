// Generate one image via MAI-Image-2e on Microsoft Foundry, save it to the repo,
// and append a record to data/gallery.json.
//
// Usage:
//   node scripts/generate-image.mjs \
//     --room room-01 \
//     --title "Quiet Morning" \
//     --note "A study of half-light against cold linen." \
//     --prompt "Oil on canvas. North-facing studio window..."
//
// Auth: Managed Identity (or `az login` locally) via DefaultAzureCredential.
//       Foundry endpoint + deployment are resolved from Key Vault (see kv-client.mjs).

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { getCredential, getFoundryConfig } from "./kv-client.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 2) {
    const key = argv[i].replace(/^--/, "");
    out[key] = argv[i + 1];
  }
  return out;
}

function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 60);
}

async function callFoundryImage({ endpoint, deployment, prompt, credential }) {
  // PLACEHOLDER: Foundry image-generation REST surface for MAI-Image-2e.
  // Replace the URL/payload shape once the exact API is confirmed for your project.
  // Auth pattern: bearer token from the AI Services scope.
  const token = await credential.getToken("https://cognitiveservices.azure.com/.default");
  if (!token) throw new Error("Failed to acquire Azure AD token for Foundry.");

  const url = `${endpoint.replace(/\/$/, "")}/images/generations?api-version=2024-10-21`;
  const body = {
    model: deployment,
    prompt,
    n: 1,
    size: "1024x1024",
    response_format: "b64_json",
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token.token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Foundry call failed: ${res.status} ${res.statusText}\n${text}`);
  }
  const json = await res.json();
  const b64 = json?.data?.[0]?.b64_json;
  if (!b64) throw new Error("No image data in Foundry response.");
  return Buffer.from(b64, "base64");
}

async function appendToGallery({ roomId, record }) {
  const galleryPath = path.join(REPO_ROOT, "data", "gallery.json");
  const gallery = JSON.parse(await fs.readFile(galleryPath, "utf8"));
  let room = (gallery.rooms ??= []).find((r) => r.id === roomId);
  if (!room) {
    room = { id: roomId, name: roomId, theme: "", images: [] };
    gallery.rooms.push(room);
  }
  (room.images ??= []).push(record);
  await fs.writeFile(galleryPath, JSON.stringify(gallery, null, 2) + "\n");
}

async function main() {
  const args = parseArgs(process.argv);
  const required = ["room", "title", "note", "prompt"];
  for (const k of required) {
    if (!args[k]) {
      console.error(`Missing --${k}`);
      process.exit(1);
    }
  }

  const credential = getCredential();
  const { endpoint, deployment } = await getFoundryConfig();
  console.log(`Generating via ${deployment} @ ${endpoint}`);

  const png = await callFoundryImage({
    endpoint,
    deployment,
    prompt: args.prompt,
    credential,
  });

  const slug = slugify(args.title);
  const id = `${args.room}-${Date.now()}-${slug}`;
  const relPath = `/gallery/${args.room}/${slug}.png`;
  const absPath = path.join(REPO_ROOT, "public", "gallery", args.room, `${slug}.png`);
  await fs.mkdir(path.dirname(absPath), { recursive: true });
  await fs.writeFile(absPath, png);

  await appendToGallery({
    roomId: args.room,
    record: {
      id,
      title: args.title,
      slug,
      path: relPath,
      artistNote: args.note,
      prompt: args.prompt,
      criticism: null,
      createdAt: new Date().toISOString(),
    },
  });

  console.log(`Saved ${relPath} and updated gallery.json`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
