// Placeholder. Routes are derived at React render time from data/gallery.json,
// so for now this script just validates the gallery is well-formed.

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");

const gallery = JSON.parse(
  await fs.readFile(path.join(REPO_ROOT, "data", "gallery.json"), "utf8")
);

let problems = 0;
for (const room of gallery.rooms ?? []) {
  if (!room.id || !room.name) {
    console.error(`Room missing id/name:`, room);
    problems++;
  }
  if ((room.images ?? []).length > 5) {
    console.error(`Room ${room.id} has more than 5 images.`);
    problems++;
  }
}

if (problems) {
  console.error(`${problems} validation issue(s).`);
  process.exit(1);
}
console.log(`Gallery OK: ${gallery.rooms.length} room(s).`);
