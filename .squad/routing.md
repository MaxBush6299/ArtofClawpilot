# Work Routing

How to decide who handles what in the Art of Clawpilot daily loop.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Gallery planning | Curator | Pick the target room, open a new room, set the next commission, retheme a room |
| Image critique | Critic | Review the newest piece, write the daily column, suggest the next direction |
| Image generation | Artist | Turn the brief into a single prompt, title, and artist note; call `scripts/generate-image.mjs` |
| Daily orchestration | Ralph | Sequence the ritual, keep the board moving, decide what runs next |
| Session logging | Scribe | Record migrations, summarize decisions, keep durable notes |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage the work and route it to the correct specialist | Ralph |
| `squad:artist` | Pick up image generation work | Artist |
| `squad:critic` | Pick up critique and evaluation work | Critic |
| `squad:curator` | Pick up planning, curation, and gallery-structure work | Curator |

### How Issue Assignment Works

1. When work arrives without a clear owner, **Ralph** triages it and routes it to the Artist, Critic, or Curator.
2. **Curator** owns planning and data-shape questions around rooms, themes, and the next brief.
3. **Critic** owns feedback quality, critique tone, and the daily suggestion to the artist.
4. **Artist** owns prompt craft and the generated piece, but never bypasses `scripts/generate-image.mjs`.
5. **Scribe** records any durable process change or migration after the substantive work is done.

## Rules

1. Start from the daily ritual and route to the agent who directly owns that step.
2. Use **Curator** first for room selection and commissions, even if another agent raised the idea.
3. Use **Critic** before changing critique schemas or image commentary conventions.
4. Use **Artist** only for the single daily piece and its immediate metadata.
5. Run **Scribe** after meaningful Squad changes or workflow migrations.
6. Use **Ralph** when the task spans multiple agents or needs sequencing rather than authorship.
