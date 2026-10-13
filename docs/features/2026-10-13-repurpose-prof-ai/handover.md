# Handover: Repurpose repo for Prof AI

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-13

## What was built
- Hackathon content removed: `docs/HACKATHON.md`, the hackathon rules and pipeline in `CLAUDE.md`, the README pitch, and the pipeline-stage prompt in the plan template.
- GitHub repo renamed to `Samrudh-Anavatti/prof-ai`. The old URL redirects, but update your remote anyway: `git remote set-url origin https://github.com/Samrudh-Anavatti/prof-ai.git`.
- Azure: `rg-insidethegame` is deleted. The new group is `rg-prof-ai` (eastus2, tag `project=prof-ai`) with budget `prof-ai-monthly`: £50/month, emails at 50% and 90% actual spend and at 100% forecast, valid until 2027-10-01.
- The workflow is unchanged.

## How to run / use it
Nothing new. `bash scripts/test.sh` still prints "No tests yet."

## Contracts other code can rely on
None.

## Tests added
None (docs only).

## Known issues / TODOs
- The project description in `CLAUDE.md` and `README.md` is a placeholder. Fill it in once the idea is settled.
- The stack is still TBD (see the 2026-10-07 repo-setup handover for the follow-ups: ADR, linter config, CI).
- The 2026-10-07 repo-setup handover still mentions `rg-insidethegame`. It's left unchanged as a historical record.

## For the other dev
Update your git remote (see above) and rename your local folder if you like. Use `rg-prof-ai` for any Azure resources.
