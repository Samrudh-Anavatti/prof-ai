# Plan: Product vision, architecture and risk docs

- **Owner:** sam
- **Branch:** `sam/repurpose-prof-ai`
- **Date:** 2026-10-14

## Goal
Capture the early Prof AI vision so both agents build from the same picture: the product loop, the business view, the direction for an Azure-first architecture, and a risk register that every feature checks against.

## Approach
Write living drafts in `docs/product/`. Make risk assessment part of the feature plan template. Keep `CLAUDE.md` flexible about the product: the only firm rules are the SE and privacy basics.

## Risks
Docs only. The one risk is accidentally committing real student data or secrets in examples; the examples are synthetic.

## Files / modules touched
- New: `docs/product/vision.md`, `docs/product/architecture.md`, `docs/product/risks.md`
- `CLAUDE.md`, `README.md`, `docs/features/_template/plan.md`, `docs/features/INDEX.md`

## Contracts added or changed
None in code. Process: feature plans now include a Risks section.

## Tests to add
None (docs only).

## Open questions
See "Open questions" in `docs/product/vision.md`.
