# Architecture (draft)

Direction only, not settled. Decisions get recorded as ADRs in `docs/decisions/` as features are built. Azure-first, because we already have App Service and Foundry quota. Keep costs low by avoiding always-on, heavyweight services.

## Components

```
Student browser ─┐                       ┌─ Foundry: chat model (small) / marking model
Tutor browser ───┼─> Web app ─> API ─────┼─ Azure AI Content Safety (Prompt Shields, harm filters)
Tutor CLI ───────┘   (App Service)       ├─ PostgreSQL flexible server (app data, usage, audit; pgvector if needed)
                                         └─ Blob storage: content store (private, read-only to agents)
Identity: Entra External ID · Secrets: Key Vault + managed identity · Telemetry: App Insights
```

- **API.** One backend service that owns auth, authorization, guardrails, budgets and every model call. The browser never talks to a model directly.
- **Guard pipeline.** Every chat turn passes through it:
  1. Auth check
  2. Lock check
  3. Rate/budget check
  4. Input length cap
  5. Prompt Shields + harm categories
  6. Topic relevance
  7. Model call
  8. Output safety
  9. Answer-leak check
  10. Log and meter

  Any step can warn, block or lock (see [risks.md](risks.md)), and every step fails closed.
- **Student agent.** A small, cheap model with read-only tools scoped to the student's current assignment. Microsoft Agent Framework or a plain tool loop with the Foundry SDK: decide in an ADR when we build it.
- **Marking.** Deterministic first (numeric answers with tolerance, multiple choice, exact match). The AI marks free-text against a rubric and returns a mark, feedback and confidence. Answer keys live in a store the student agent can't read.
- **Tutor tooling.** A CLI/scripts in Phase 1 (upload content, create assignments, review, unlock), plus a read-only tutor dashboard for transcripts, results and usage.

## Content store instead of an enterprise search index

Indexing the whole library into an always-on search service is expensive and mostly wasted, because a student only ever needs the chapter they're on. Instead:

**1. A folder-structured content store in Blob**, with small manifest files so an agent (or code) can navigate it cheaply:

```
content/
  curricula/<curriculum>/<subject>/<grade>/syllabus.md     topic list, links to chapters
  books/<book>/manifest.json                                title, licence, chapter list
  books/<book>/chapters/<nn-slug>/text.md                   extracted once, on first use
  books/<book>/chapters/<nn-slug>/figures/                  diagrams (Phase 2)
  books/<book>/chapters/<nn-slug>/chunks.json               chunk text + embeddings, built lazily
  worksheets/<slug>/questions.json                          visible to student agent
answer-keys/                                                separate container; marking only
```

**2. Lazy ingestion.** A chapter is extracted to markdown (e.g. with Document Intelligence, priced per page) and chunked only when a tutor first assigns it. We pay per chapter used, not per library.

**3. Tiered context for the assistant:**
  1. **Chapter in context.** A chapter is typically small enough to fit in the prompt. With prompt caching, this is cheap and gives the strongest grounding. This is the default.
  2. **Traversal.** The agent reads the manifest/syllabus to pull a linked section or prerequisite topic.
  3. **Session vector lookup.** For large material, load that chapter's `chunks.json` and run a similarity search in-process. Move to pgvector only if that gets slow. No search service.

**4. Isolation by storage, not prompts.** The student agent's identity can read `content/` but not `answer-keys/`, and can only fetch paths under its current assignment.

## Cost levers

- A small model by default; a larger one only for marking edge cases.
- Prompt caching for the chapter context; truncate or summarise long chats.
- Per-student token budgets enforced in the API; global monthly cap; Azure budget alert on `rg-prof-ai`.
- Cheap tiers: App Service B-tier, Postgres Burstable, Blob hot/cool, Entra External ID (free at our scale).

## To decide (ADRs)

- **Languages:** probably Python (FastAPI) for the API plus TypeScript (React) for the web app.
- **Agent framework:** Microsoft Agent Framework or a plain Foundry SDK tool loop.
- **Models:** the chat model and the marking model, picked from what's deployable in Foundry at the time, by cost.
- **Data store:** Postgres, or Cosmos DB serverless.
- **Rate limiting:** API Management (has LLM token-limit policies) or limits in the app.
- **IaC:** Bicep.
