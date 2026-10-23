# Plan: Nice-to-have list

- **Owner:** punji
- **Branch:** `docs/nice-to-have`
- **Date:** 2026-10-23

## Goal
Good ideas come up while we build, and some of them wait on money rather than work: a paid service, a bigger App Service plan, hardware. They need somewhere to live that isn't the INDEX, which lists work we will do. Also record the order of Punji's next features, so Sam can see what's coming.

## Approach
- **`docs/product/nice-to-have.md`:** one entry per idea, saying what it is, why it's good, what it would need and what it depends on. The first entry is voice input (speech-to-text, like Wispr Flow).
- **`CLAUDE.md`:** a rule that agents offer to record a good idea that isn't core now, and add it once the person agrees. A "Later:" INDEX row if it only needs building; `nice-to-have.md` if it waits on money.
- **INDEX:** the "Later:" rows stay where they are, because they need building, not funding (Punji, 2026-10-23). Add `planned` rows for Punji's next features, in order: Prof AI speaks, a personal intro to each question, app-wide uplift, skill tags, adaptive practice. The adaptive-practice row replaces the old Anki-style "Later:" row with Punji's narrower scope.
- **README:** a link to `nice-to-have.md`, the next features under "Where we are", and the 🆕 Latest section.

## Risks
Docs only, so no new abuse, cost, data or child-safety risk. The voice-input entry records its own risks (R10, R16) for whoever picks it up.

## Learning check
No principle applies directly. The adaptive-practice row's narrower scope leaves L9 (spaced practice) and L10 (interleaving) without a plan, so `learning-science.md` now says so instead of pointing at the old row.

## Files / modules touched
- `docs/product/nice-to-have.md` (new), `docs/product/learning-science.md`
- `docs/features/INDEX.md`, `CLAUDE.md`, `README.md`

## Contracts added or changed
None.

## Tests to add
None: no code changes.

## Open questions
- Move the INDEX's "Later:" rows into `nice-to-have.md`, or keep them? Kept (Punji): they need building, which makes them a different category from ideas that wait on funding.
