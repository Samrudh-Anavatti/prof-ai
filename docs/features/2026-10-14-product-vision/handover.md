# Handover: Product vision, architecture and risk docs

- **Owner:** sam
- **PR:** https://github.com/Samrudh-Anavatti/prof-ai/pull/1
- **Merged:** 2026-10-14

## What was built
- `docs/product/vision.md`: the weekly tutoring loop, principles, phased roadmap, business view and open questions.
- `docs/product/architecture.md`: the direction for an Azure-first architecture.
  - A guard pipeline in front of every model call.
  - A Blob content store with lazy ingestion and tiered context (chapter in prompt → traversal → small per-chapter vectors), instead of an enterprise search index.
  - Answer keys isolated from the student agent at the storage level.
- `docs/product/risks.md`: design stances, lock levels (including a safeguarding exception), the risk register (R1–R15) and a per-feature risk checklist.
- The plan template now has a **Risks** section. `CLAUDE.md` describes the product and adds a "no real student data in the repo" rule.

## How to run / use it
Read `docs/product/` before planning a feature. Fill in the Risks section of `plan.md` using the checklist in `risks.md`.

## Contracts other code can rely on
None yet.

## Tests added
None (docs only).

## Known issues / TODOs
- No ADRs yet. Record the first concrete stack choices (languages, agent framework, models, data store) when the first feature is planned.
- The open questions in `vision.md` need answers from Sam and Punji, especially jurisdiction, content licences and the safeguarding escalation process. These must be settled before any real student uses the platform.

## For the other dev
Everything in `docs/product/` is a draft. If you disagree, change it in your branch and say so in your handover.
