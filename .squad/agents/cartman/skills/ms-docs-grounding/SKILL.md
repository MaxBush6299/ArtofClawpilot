---
name: "ms-docs-grounding"
description: "Ground every Microsoft/Azure technical claim, code sample, and recommendation in official Microsoft Learn documentation using the microsoftdocs MCP tools. Cite sources and dates on output."
domain: "documentation, microsoft, azure, grounding"
confidence: "high"
source: "manual"
tools:
  - name: "microsoft_docs_search"
    description: "Search official Microsoft/Azure docs and return up to 10 short, citable excerpts."
    when: "Whenever you need to validate a Microsoft/Azure fact, find the canonical guidance for a service, or locate a starting page for deeper reading."
  - name: "microsoft_docs_fetch"
    description: "Fetch a full Microsoft Learn page as markdown."
    when: "After search identifies a high-value page and you need complete steps, prerequisites, or reference detail."
  - name: "microsoft_code_sample_search"
    description: "Search for official Microsoft/Azure code snippets, optionally filtered by language."
    when: "Whenever you are about to write or recommend Microsoft/Azure-related code. Always run this before authoring sample code from memory."
---

## Context

Use this skill any time the work touches a Microsoft or Azure product, SDK,
service, framework, or developer tool — Azure services, .NET, C#, Microsoft
Graph, Microsoft 365, Power Platform, Visual Studio / VS Code, GitHub-on-Azure,
Entra ID, Foundry, Aspire, etc. The default behavior is **"don't answer from
memory; search first."**

Apply this skill when:

- Recommending a service, SDK, or pattern.
- Writing or reviewing Microsoft/Azure-specific code.
- Producing demos or learning docs (the other two solution-engineer skills
  delegate to this one for citations).
- The user asks "how do I…" against a Microsoft product.

## Patterns

### 1. Search → fetch → cite

1. Run `microsoft_docs_search` with a precise query (service name + scenario).
   Read the returned excerpts.
2. If a result looks like the canonical page for the answer, follow up with
   `microsoft_docs_fetch` on its URL to get the complete content.
3. For any code you write, run `microsoft_code_sample_search` with `language`
   set, and prefer the official snippet over inventing one.

### 2. Always cite

Every Microsoft/Azure claim or code block in your output gets a citation:

```markdown
> Source: [Page title](https://learn.microsoft.com/...) — fetched YYYY-MM-DD
```

At the end of a longer response, include a **Sources** section listing each
URL once.

### 3. Prefer first-party

If a search returns both Microsoft Learn pages and third-party blogs, cite the
Microsoft Learn page. Use third-party sources only when first-party docs
genuinely don't cover the topic, and label them clearly.

### 4. Acknowledge gaps

If `microsoft_docs_search` returns nothing relevant after two reasonable
queries, **say so explicitly** — "Microsoft Learn does not appear to document
this scenario; here is the closest related guidance: …". Don't paper over it
with inferred answers.

### 5. Date-stamp guidance

Microsoft services move fast. Include the fetch date next to each citation so
the reader knows how fresh the grounding is.

## Examples

**Recommending an Azure service**

> User: "What's the best way to host a containerized API on Azure with scale-to-zero?"
>
> Agent runs `microsoft_docs_search` for "Azure Container Apps scale to zero",
> reads excerpts, fetches the
> "Scaling in Azure Container Apps" page, then answers with the canonical
> guidance and links the page.

**Writing a snippet**

> Before writing a `BlobServiceClient` example, run
> `microsoft_code_sample_search` with query `"BlobServiceClient upload"` and
> `language: "csharp"`. Use the returned official snippet as the basis.

## Anti-Patterns

- ❌ Answering Microsoft/Azure questions from memory without searching.
- ❌ Citing only a top-level marketing page when a deeper Learn article exists.
- ❌ Inventing API surface (method names, parameter shapes) instead of fetching
  the reference page.
- ❌ Stripping URLs from quoted material — always preserve attribution.
- ❌ Pretending the docs say something they don't. If grounding is weak, label
  the answer as inferred.
