# Plan: Repurpose repo for Prof AI

- **Owner:** sam
- **Branch:** `sam/repurpose-prof-ai`
- **Date:** 2026-10-13

## Goal
We've dropped the "Inside the Game" hackathon. Reuse this repo and its agent workflow for the new project, Prof AI.

## Approach
- Remove hackathon-specific content and keep the workflow (feature docs, regression suite, git and style rules) unchanged.
- Rename the GitHub repo to `prof-ai`.
- Azure resource groups can't be renamed, so create `rg-prof-ai` with the same budget alert and delete `rg-insidethegame`, which was empty.

## Files / modules touched
- `CLAUDE.md`, `README.md`, `.env.example`, `docs/features/_template/plan.md`, `docs/features/INDEX.md`
- Delete `docs/HACKATHON.md`

## Contracts added or changed
None.

## Tests to add
None. This change is docs only.

## Open questions
- What Prof AI does and who it's for.
- Stack.
