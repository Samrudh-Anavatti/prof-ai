# Handover: Repo setup

- **Owner:** Sam
- **Merged:** 2026-10-07 (initial commit)

## What was built
- Repo skeleton: `docs/`, `src/`, `tests/`, `infra/`, `data/`, `scripts/`
- `CLAUDE.md` with agent conventions: the feature plan/handover workflow, the shared regression suite, style rules, and secrets handling
- `docs/HACKATHON.md`: a condensed version of the official rules
- Feature templates in `docs/features/_template/` and the status table in `docs/features/INDEX.md`
- `scripts/test.sh`: a single entrypoint for the whole test suite. It runs pytest if `tests/test_*.py` files exist and `npm test` for every `package.json`
- Azure resource group `rg-insidethegame` (eastus2), tagged `project=insidethegame`, with a monthly cost budget alert

## Known issues / TODOs
- The stack isn't chosen yet. After whiteboarding, record it in `CLAUDE.md` and `docs/decisions/0001-stack.md`, then add linter config (ruff/eslint) and CI.
- CI isn't set up yet. Once tests exist, add a GitHub Action that runs `scripts/test.sh` on PRs.

## For the other dev
Clone, read `CLAUDE.md`, then start each feature by copying `docs/features/_template/`.
