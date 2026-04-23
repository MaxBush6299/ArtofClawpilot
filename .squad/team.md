# Team — Art of Clawpilot

A three-person studio that produces and curates one new museum-grade piece per day for the gallery hosted in this repo.

## Members

| Name | Role | Charter | Status |
|---|---|---|---|
| Artist | Image generation (MAI-Image-2e via Foundry) | `.squad/agents/artist/charter.md` | ✅ Active |
| Critic | Text reasoning and image criticism | `.squad/agents/critic/charter.md` | ✅ Active |
| Curator | Gallery planning and file management | `.squad/agents/curator/charter.md` | ✅ Active |
| Scribe | Session logging | `.squad/agents/scribe/charter.md` | 📋 Silent |
| Ralph | Work monitor | `.squad/agents/ralph/charter.md` | 🔄 Monitor |

## Project Context

- **Owner:** Max Bush
- **Stack:** React 18, TypeScript, Vite, React Router, Node scripts, Azure Identity/Key Vault helpers, Static Web Apps config
- **Description:** A daily gallery workflow where custom Squad agents commission, critique, and generate one new museum-grade piece for the site.
- **Created:** 2026-04-23

## Daily Ritual

When invoked every morning by the Clawpilot automation:

1. **Curator** opens `data/gallery.json` and `data/next-brief.json`. Decides which room the next piece belongs in, whether a new room is needed (rooms cap at 5 pieces), and what style/theme to commission. Writes the updated brief to `data/next-brief.json`.
2. **Critic** opens the most recently added image (if any) and writes a column entry into `data/critiques.json` and into the image's `criticism` field on `data/gallery.json`. Skipped on Day 1.
3. **Artist** reads `data/next-brief.json` plus the latest critique. Crafts a single image prompt (museum-grade fine art only — oil, watercolor, mixed media, photography, sculpture studies; never memes, mockups, logos, or UI). Calls `node scripts/generate-image.mjs --prompt "..." --room <id> --title "..."`. The script saves the PNG to `public/gallery/<room>/<slug>.png` and appends a record to `data/gallery.json`.
4. After all three have run, `node scripts/rebuild-routes.mjs` regenerates any derived data, and the orchestrator commits and pushes.

## Shared Rules

- All inter-agent communication happens through JSON files in `data/`. No verbal hand-offs — if it isn't on disk, it didn't happen.
- Never call image generation directly; always go through `scripts/generate-image.mjs` so auth (Managed Identity -> Key Vault -> Foundry) is consistent.
- One new image per day. If the artist produces nothing usable, log the reason in `data/gallery.json#skipped` and exit clean.
- Pieces are always museum-quality. No commercial work, no UI mockups, no text-heavy posters.

## Invocation

```
copilot --agent squad --yolo
```

The Clawpilot automation that schedules this is documented in the project README.
