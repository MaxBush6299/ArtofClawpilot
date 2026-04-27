# Frontend hosted update guide

> Status: corrected frontend sign-off guide for issue #15 smoke proof.

This guide explains what the hosted daily-run adds to `data/gallery.json`, what the current frontend actually does with that data, and how Max can verify the hosted smoke branch without assuming behavior the app does not implement.

---

## What changed in the data contract

The hosted orchestrator can grow `data/gallery.json` in two ways:

| Surface | What it means | Frontend impact |
| --- | --- | --- |
| Top-level `skipped[]` | Durable ledger of structured skip outcomes for a `runDate`. | Current frontend ignores it. No user-facing UI reads it. |
| Additional image metadata | Published images now carry audit fields such as `runDate`, `model`, `promptSummary`, and optional `reasoningModel`. | Current frontend tolerates the extra fields because it only reads a smaller subset of image properties. |

### Important format notes

- `runDate` is a **day key in `YYYY-MM-DD` format**, not a full ISO timestamp.
- `createdAt` is still the timestamp-like field used for display on the Room page.
- `skipped[]` is part of the ledger contract, but not part of the browsing experience today.

---

## What Home.tsx actually reads

**File:** `src/pages/Home.tsx`

Current behavior:

- Reads `gallery.rooms ?? []`
- For each room, uses `r.images?.[0]` as the cover image
- Shows `r.name`
- Shows `r.images?.length ?? 0`
- Does **not** read `gallery.skipped`
- Does **not** read `runDate`, `model`, `reasoningModel`, or `promptSummary`

### Practical implication for hosted smoke

Home does **not** automatically show the newest published image as the room cover.

Why:

- The orchestrator appends new images to `room.images`
- Home reads `images[0]`
- So the cover stays the **first** image in the array, not the newest appended one

That means:

- If the target room was empty before the smoke publish, the new image becomes `images[0]`, so it will appear as the Home cover.
- If the target room already had images, the new publish usually increases the room count, but the Home cover will remain the earlier first image unless the array order changes.

For smoke sign-off, treat **room count growth** as the reliable Home-page signal. Treat **cover-image change** as expected only when the room was previously empty or the data was reordered separately.

---

## What Room.tsx actually reads

**File:** `src/pages/Room.tsx`

Current behavior:

- Finds a room from `gallery.rooms`
- Maps `room.images ?? []`
- Renders `img.path`, `img.title`, `img.artistNote`, and `img.createdAt`
- Renders criticism only when `img.criticism` is truthy
- Does **not** use optional chaining for `img.criticism`; it uses a conditional render: `{img.criticism && (...)}`
- Does **not** read `runDate`, `model`, `reasoningModel`, or `promptSummary`

### Practical implication

Room is already tolerant of the hosted metadata expansion because it simply ignores the new fields. If `img.criticism` is absent, the critique block does not render.

---

## What the static JSON import does and does not prove

**Files:** `src/pages/Home.tsx`, `src/pages/Room.tsx`

Both pages statically import `../../data/gallery.json`.

That gives you:

- a build-time/load-time guarantee that the JSON is present and parseable enough for the app bundle to consume it
- a simple read path with no runtime fetch logic

That does **not** give you:

- full structural validation of the gallery contract
- proof that required hosted fields are present
- proof that `skipped[]` or image metadata matches the orchestrator schema

Structural contract validation belongs to the orchestrator and the hosted validation gates in `docs/architecture/hosted-validation-gates.md`, not to the frontend import itself.

---

## Frontend verdict on the current contract

For the current hosted contract, no frontend code change is required.

Why that is true:

- Top-level `skipped[]` is ignored by both pages.
- Extra image fields do not break either page because neither page depends on them.
- Room gracefully omits the critique block when `criticism` is missing.
- Home continues to work with appended images; it just does not surface “newest image as cover” semantics.

What is **not** true:

- The frontend is not validating the hosted schema for you.
- The Home page is not a reliable proof that the newest publish became the cover image.

---

## Recommended smoke-proof checklist for Max

Use this when validating the `hosted-smoke` branch after Phase B and Phase C from `docs/architecture/hosted-smoke-checklist.md`.

### Before smoke validation

- [ ] Confirm `npm run build` succeeds on the branch.
- [ ] Confirm `data/gallery.json` still parses and contains `rooms` plus optional `skipped`.
- [ ] Note whether the target room is empty before Phase B. That determines whether a Home cover change should happen.

### After Phase B (durable publish)

Validate the data first:

- [ ] Confirm exactly one new image entry exists for the smoke `runDate`.
- [ ] Confirm the new image includes required publish metadata from the hosted contract, including `runDate`, `model`, `promptSummary`, `artistNote`, and `createdAt`.
- [ ] Confirm `runDate` is formatted as `YYYY-MM-DD`.
- [ ] Confirm no skip record exists for that same `runDate`.

Validate the frontend next:

- [ ] Build the app: `npm run build`
- [ ] Start the app locally if needed: `npm run dev`
- [ ] On Home, confirm the room count increased for the room that received the new image.
- [ ] On Home, only expect the cover image to change if that room had been empty before the publish.
- [ ] Open the target room and confirm the new image appears in the room grid.
- [ ] Confirm the Room page renders title, artist note, and displayed date without errors.
- [ ] Confirm there is no user-facing rendering of `skipped[]`.

### After Phase C (durable skip path)

Validate the data first:

- [ ] Confirm exactly one new skip record exists for the Phase C `runDate`.
- [ ] Confirm no image was published for that same `runDate`.
- [ ] Confirm the gallery still satisfies the one-outcome-per-run-identity invariant with skip-closes-day semantics for the tested date.

Validate the frontend next:

- [ ] Build the app again: `npm run build`
- [ ] Confirm Home still renders rooms and counts normally.
- [ ] Confirm Room pages still render existing images normally.
- [ ] Confirm skip records remain invisible in the browsing UI.

---

## Sign-off statement

If the checks above pass, the frontend sign-off can say:

> **Frontend smoke proof passed.** The current UI tolerates hosted `gallery.json` growth, including top-level `skipped[]`, extra image audit fields (including `runId`), and multiple images per `runDate` with distinct `runId` values. Home remains count-correct but does not guarantee newest-image cover behavior because it reads `images[0]` while the orchestrator appends new images. Room rendering remains stable and ignores the hosted audit fields.

---

## Future-only improvements (not required now)

Consider follow-up frontend work only if the product wants it:

1. **Newest image as Home cover:** change Home to intentionally select the latest image rather than `images[0]`.
2. **Typed gallery contract:** add shared frontend types for image and skip records.
3. **Operator visibility for skips:** add a separate admin/operator surface if skip history ever needs to be visible.

None of those are required for current hosted smoke sign-off.