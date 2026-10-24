# Handover: Nice-to-have list

- **Owner:** punji
- **PR:** see the PR for `docs/nice-to-have`
- **Merged:** 2026-10-23

## What was built
As planned:
- `docs/product/nice-to-have.md`, with voice input as its first entry;
- a CLAUDE.md rule, "Ideas for later";
- five `planned` INDEX rows for Punji's next features, in order;
- the old Anki-style adaptive-practice "Later:" row is gone, replaced by the new adaptive-practice row;
- `learning-science.md`'s L9 and L10 rows no longer point at the old row.

## How to run / use it
When an idea comes up that sounds good but isn't core now, the agent asks whether to record it. Work we'll do anyway goes in the INDEX as a `planned` "Later:" row; an idea that waits on money goes in `nice-to-have.md`.

## Contracts other code can rely on
None.

## Tests added
None: docs only. The suite is unchanged at 364 pytest and 122 vitest, all passing.

## Known issues / TODOs
- Spaced practice (L9) and interleaving (L10) have no planned feature now that adaptive practice is narrower. Worth a "Later:" row if we still want them.

## For the other dev
- **Sam:** the new CLAUDE.md rule applies to your agent too. The next five INDEX rows are Punji's plan. Skill tags changes what the knowledge graph is for, and adaptive practice needs a question bank, so Punji will talk to you before planning either.
