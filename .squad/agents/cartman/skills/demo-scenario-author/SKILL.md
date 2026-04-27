---
name: "demo-scenario-author"
description: "Produce step-by-step click-through demos of the actual running application in the repo — UI clicks, API calls, or CLI commands as appropriate — so a solution engineer can demo the capability live. Output goes to docs/demos/<scenario>.md."
domain: "documentation, demos, enablement, solution-engineering"
confidence: "high"
source: "manual"
tools: []
---

## Context

Use this skill when the user asks for a **demo** of the application that lives
in this repo. The deliverable is a script the solution engineer (or anyone on
the team) can follow against the **running application** — clicking buttons,
sending requests, or typing commands — to demonstrate a specific capability
or concept end-to-end.

A "scenario" is a single user-facing outcome demonstrated by exercising the
**actual app**, not a code reading. Examples:

- *"Upload a file and watch it get classified by the pipeline."*
- *"Authenticate with Entra ID and call a protected endpoint."*
- *"Trigger a retry by killing the worker mid-job."*

This skill **does not invent features**. Before writing, inspect the repo to
confirm the capability exists and to learn how to exercise it (which port it
runs on, which endpoints exist, which UI screens are reachable, which CLI
verbs are wired up).

If the demo touches Microsoft/Azure technology, **delegate citations to the
`ms-docs-grounding` skill** for any external/conceptual references.

## Patterns

### Pick the modality based on what the app actually exposes

Inspect the repo and choose the demo modality that matches reality:

| Repo evidence | Demo modality |
|---|---|
| Web frontend (React/Blazor/Razor/MVC views) | **UI click-through** — describe screens, buttons, form values |
| HTTP API only (no UI), OpenAPI/Swagger, controllers/endpoints | **API click-through** — `curl`/`Invoke-RestMethod`/REST Client `.http` requests |
| CLI / console app, `Program.cs` with command parsing, `commander`, `cobra`, etc. | **CLI walk-through** — exact commands and flags |
| Multiple surfaces (e.g. web + API) | Pick the most demoable surface for the scenario; mention the other as an alternative |
| Background worker / queue consumer with no direct surface | Demo via the **trigger** (drop a message, upload a file) and the **observable effect** (logs, DB row, downstream call) |

If the repo can't actually be run as-is (missing setup, broken state), **say
so loudly** in the demo's Prerequisites section and stop — don't fake it.

### Output location and naming

- Write demos to `docs/demos/<kebab-case-scenario>.md` in the target repo.
- Create the folder if it doesn't exist.
- One scenario per file. Don't merge multiple scenarios.

### Required sections (in this order)

```markdown
# Demo: <Scenario Title>

> One-sentence outcome statement: what the audience will see by the end.

**Modality:** UI / API / CLI / mixed
**Capability demonstrated:** <feature name as it appears in the codebase>
**Concepts demonstrated:** <e.g. Entra ID auth, retry policies, queue fan-out>
**Time-to-run:** <rough estimate>

## Audience & Goal
- Primary audience: solution engineer running the demo (you).
- Adapt-for-customer notes: short bullets calling out what to omit/rephrase
  when re-using this for a customer audience.
- What the audience will be able to explain or do afterward.

## Prerequisites
- Software, accounts, env vars, sample data needed before starting.
- Exact versions where they matter.
- Whether internet/cloud resources are required, and the cost shape.

## Setup — get the app running
Concrete commands to bring the app to the demo's starting state. Prefer one
copy-pasteable block.

```<shell>
<commands to clone / restore / build / run, plus the URL/port to open>
```

**Verify you're ready:** one observable signal (a URL responds, a log line
appears) that proves setup worked.

## Walkthrough

### Step 1 — <verb-led title>
**What we're showing:** one sentence — capability *and* underlying concept.
**Do this (UI):** "Click **Upload**, choose `samples/invoice.pdf`, click **Submit**."
**Do this (API):**
```http
POST {{baseUrl}}/api/invoices
Content-Type: multipart/form-data
...
```
**Do this (CLI):** `myapp ingest ./samples/invoice.pdf`
**Expected:** what the audience should see — exact UI state, response body,
log line, DB change.
**Talking point:** the *why* — what concept this proves, what design choice
made it work, what would break if it were done differently.
**Source pointers:** relative file paths in the repo where the audience could
go to read the implementation later.

### Step 2 — ...
(repeat — each step builds on the previous app state)

## Recap
- Bullet list mapping what just happened back to the **capability** and
  **concepts** declared in the header.

## Reset / Cleanup
How to return the app to a clean state so the demo can be re-run, plus how to
tear down any cloud resources spun up.

## Troubleshooting
- Common failure → cause → fix.

## Adapt for a Customer Audience
- 3-5 bullets: what to skip, what to emphasize, what NOT to expose
  (debug endpoints, internal config, hard-coded data).

## References
- Source files exercised in the demo (relative paths).
- Microsoft Learn links for any cited concepts (cite via ms-docs-grounding,
  with date).
```

### Click-through fidelity

The demo must be reproducible by a human who has never seen the app:

- For **UI** steps: name the exact button/link/menu item, the exact field
  values, and the exact screen state to expect. No "configure as needed".
- For **API** steps: prefer a self-contained `.http` (REST Client) or
  `curl` block. Show the request *and* a sample of the response. Mark
  variables (`{{baseUrl}}`, `{{token}}`) explicitly.
- For **CLI** steps: full command line including flags. Show expected stdout.

### Capability vs. concept

Every step has both:

- **Capability** — the feature the app shipped (e.g. "uploads route to the
  classifier").
- **Concept** — the architectural/Microsoft-tech idea it embodies (e.g.
  "fan-out to a Service Bus topic", "Managed Identity to Storage").

The Talking point ties the two together. This is what makes the doc useful
beyond the demo itself — and what lets you repurpose pieces for customers.

### Source pointers, not source dumps

For each step, list the 1-3 files in the repo that implement what just
happened. Don't paste the implementation — link to it. The reader runs the
demo first and reads the code second.

### Voice

Direct, second-person ("Click", "Send", "Run", "You should see"). No
marketing. No "simply" or "just". Honest about gotchas and current state of
the app.

## Examples

A request like *"Create a demo of the invoice-upload classification flow"*
against a repo with a Blazor frontend + Functions API should produce
`docs/demos/invoice-upload-classification.md` with:

- Modality marked **mixed (UI + API)** because the visible flow is in the
  Blazor app but the interesting part to talk through is the Functions
  binding.
- Setup that runs `dotnet run` on the host project and opens
  `https://localhost:5001`.
- Step 1: click Upload, pick `samples/invoice.pdf`, watch the result tile
  appear → talking point about the SignalR push.
- Step 2: open the Functions log → talking point about the Service Bus
  binding and Managed Identity.
- Reset block that empties the Storage container.
- Adapt-for-customer notes saying to hide the dev-mode telemetry overlay.

## Anti-Patterns

- ❌ Inventing UI screens, endpoints, or commands that don't exist in the
  repo.
- ❌ Demos that read code instead of running the app. Code reading belongs
  in `learning-doc-author`.
- ❌ Vague steps like "configure the settings" or "trigger the workflow".
  Name the exact click, request, or command.
- ❌ Skipping **Expected** state — without it the audience can't tell if the
  demo worked.
- ❌ Demos that depend on undocumented secrets ("paste your key here") with
  no guidance on what kind of key, where to get it, or what scopes it needs.
- ❌ Combining multiple unrelated scenarios into one file.
- ❌ Marketing language. The output is a working demo script, not a pitch.
- ❌ Skipping the **Adapt for a Customer Audience** section — the SE will
  re-use this material with customers and needs the safety bullets.
