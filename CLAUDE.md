# CLAUDE.md

Instructions for every coding agent (Claude Code, Copilot, etc.) working in this repo. Two humans (Sam and Punjy) build features in parallel on their own time, each driving an agent. This file and `docs/features/` are how the two agents stay in sync. **Keep this file current.** If you change a convention, command, folder, or architecture decision, update this file in the same branch.

## Project

**Prof AI**: an AI-assisted tutoring platform for grades 6–12. A human tutor teaches a lesson and assigns a chapter and questions. During the week, each student works on the platform: they submit answers, which are marked by software/AI and reviewed by the tutor, and they chat with their own heavily guarded assistant, grounded in the tutor's content. The tutor sees results, transcripts and usage. The first users are Sam and Punjy as tutors, with 5–6 students each.

The product is an early vision. `docs/product/` (vision, architecture, risks) is a living draft, not a rulebook. Question it, and update it when the idea moves.

- **Risk-first.** Every feature plan covers abuse, cost, data, correctness and child-safety risks before any code (see `docs/product/risks.md`).
- Stack ([ADR 0001](docs/decisions/0001-stack.md), [ADR 0002](docs/decisions/0002-auth-and-users.md), [ADR 0003](docs/decisions/0003-frontend.md), [ADR 0004](docs/decisions/0004-invites-and-sign-up.md), [ADR 0005](docs/decisions/0005-models-and-context-budget.md)): Python 3.11 + FastAPI on App Service Linux B1 (`https://prof-ai.azurewebsites.net`), Microsoft Foundry (`gpt-5.6-luna`), Blob storage, Cosmos DB serverless, Entra External ID sign-in (`profai.onmicrosoft.com`) via App Service Authentication, with open email-code sign-up gated by tutor invites in the app's `users` container. Bicep for infrastructure, GitHub Actions for CI/CD. Frontend: React + TypeScript (Vite) in `web/`, built into `src/prof_ai/static/` and served by FastAPI from the same origin. Direction for the rest is in `docs/product/architecture.md`; record new choices as ADRs and summarise them here.
- No keys in code or config: services use managed identity, deploys use GitHub OIDC, and local dev uses your `az login` identity. The one unavoidable secret (App Service Authentication's client secret) lives in Key Vault; rotate it with `scripts/rotate_auth_secret.py`.
- **Every endpoint except `/healthz` and the static frontend shell must depend on `prof_ai.auth.CurrentUser` (or `require_role`).** That's where the invite check and account locks are enforced. All JSON endpoints live under `/api/`; a regression test fails if one doesn't require sign-in. The shell carries no data.
- Azure resource group: `rg-prof-ai` (UK South, subscription "Subscription 1", £50/month budget alert, all defined in `infra/main.bicep`). Every resource must go in this group with tags `project=prof-ai` and `owner=<sam|punjy>`.

## Start of every session

1. `git pull` on `master`, then branch (see Git workflow).
2. Read `docs/features/INDEX.md`. Then read the `handover.md` of every feature merged since you last worked, especially the other person's. Their handovers list contracts, gotchas and anything they need from you.
3. Run the full test suite (see Testing) **before** making changes so you know the baseline is green.

## Feature workflow (required)

Every feature, however small, gets a folder: `docs/features/YYYY-MM-DD-<short-slug>/`, created from `docs/features/_template/`.

1. **Before coding**, write `plan.md`: goal, approach, risks and their controls, files/modules touched, interfaces or contracts you'll add or change, the tests you'll add, and open questions. Add a row to `docs/features/INDEX.md` with status `in-progress`.
2. Build the feature on its branch.
3. Add regression tests (see Testing).
4. **Before merging**, write `handover.md`: what was actually built (and how it differs from the plan), how to run or use it, contracts other code now relies on, the tests added, known issues or TODOs, and anything the other person needs to know or do. Set the INDEX row to `merged`.
   - **Update `README.md`:** replace the **🆕 Latest** section with your feature (date, owner, what changed, links to plan and handover), and move the previous one into the "Earlier features" table. Also update "Where we are", "Open items" and the architecture diagram or access table if your feature changed them. The README is how the other person sees what changed without reading every handover.
5. Run the full test suite. Only merge if it's green.

Don't skip the docs. The other person's agent depends on them because it wasn't there for the work.

## Git workflow

- Default branch is `master`. Don't commit directly to it.
- Branch names: `<owner>/<short-slug>`, e.g. `sam/event-ingest` or `punjy/fan-overlay`.
- Merge to `master` through a PR. The PR description links the feature's `plan.md` and `handover.md`.
- Keep branches short-lived. Rebase on or merge `master` before opening the PR, and re-run the suite after.
- Commit messages are short and imperative: "Add login endpoint", not "added stuff".

## Local setup and commands

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # .venv/bin/python on macOS/Linux
cp .env.example .env
(cd web && npm ci)                                             # frontend deps (Node 22)
bash scripts/test.sh                                           # full suite (pytest + vitest)
.venv/Scripts/python -m uvicorn prof_ai.main:app --app-dir src --reload --env-file .env
(cd web && npm run dev)                                        # Vite on :5173, proxies /api to :8000
(cd web && npm run build)                                      # or build once and use :8000 alone
bash scripts/deploy-infra.sh --what-if                         # preview infra changes, then run without the flag
```

Tutor CLI (installed by `requirements-dev.txt` into the venv, so run it as `.venv/Scripts/prof` from the repo root or activate the venv first; needs `az login` and `STORAGE_ACCOUNT_URL` in `.env`):

```bash
.venv/Scripts/prof content add-book book.pdf --slug maths-9-core --title "Maths 9" --subject maths --grades 9 --licence-type licensed
.venv/Scripts/prof content list
.venv/Scripts/prof content show maths-9-core
.venv/Scripts/prof users add --email alex@example.com --name Alex --role student --tutor <tutor email>  # invite; they sign up with an email code
.venv/Scripts/prof users list
.venv/Scripts/prof users lock alex@example.com --reason "Prompt injection attempt"
.venv/Scripts/prof users unlock alex@example.com
.venv/Scripts/prof users remove alex@example.com                          # deletes account, chats, usage, profiles
.venv/Scripts/prof users set-admin sam@example.com [--revoke]             # admins manage everyone at /users
.venv/Scripts/prof profiles set alex@example.com --profile alex.md        # what the AI is told about Alex
.venv/Scripts/prof profiles set sam@example.com --teaching-style style.md # tutors: applies to their students
.venv/Scripts/prof profiles show alex@example.com                         # files + full system prompt
.venv/Scripts/prof chats list alex@example.com
.venv/Scripts/prof chats show alex@example.com <conversation-id>
.venv/Scripts/prof eval dilution                                         # dry run: prints cases and worst-case cost
.venv/Scripts/prof eval dilution --yes                                   # calls Luna (~$0.10-0.85, capped by --max-usd); needs FOUNDRY_ENDPOINT
```

Tutors can also edit their teaching style in the web app at `/teaching-style` (`GET`/`PUT /api/teaching-style`, tutors only, audited). The app's identity can write only to the `profiles` container.

Tutors manage accounts at `/users` (`/api/users`): admins manage everyone; other tutors manage only their own students. The web app never calls Graph. **Any new per-user data must be erased in `main.user_data_eraser`**, so deleting a user really deletes their data.

The tutor chat calls Luna through `prof_ai.chat`. Every model call must go through `ChatService`, which enforces the input cap, budgets, kill switch and rate limit before calling the model. Locally it uses your `az login` and costs real tokens.

**Everything sent to the model is built by `prof_ai.chat.context.assemble` from capped layers ([ADR 0005](docs/decisions/0005-models-and-context-budget.md)).** Lessons get 64k estimated tokens and knowledge-graph reference material 64k per turn, under a 256k ceiling. Enforce a layer's cap where its content is written (e.g. refuse a lesson save over 64k, measured with `estimate_tokens`), and pass it in through `ContextInput`; never build prompts elsewhere. A new layer or model needs an ADR 0005 update, a `LAYER_CAPS` entry or `ModelProfile`, and must pass `check_budget`. Budgets are in dollars (`CHAT_DAILY_USER_USD`, `CHAT_DAILY_GLOBAL_USD`); tutors are exempt per user.

Evals (`prof_ai.evals`, `prof eval ...`) are the one exception to going through `ChatService`: they run locally on your `az login` with synthetic data, use the same `assemble`, and have their own hard spend cap. Re-run `prof eval dilution` when you change the model, the base prompt or the caps.

For local runs without signing in, set `DEV_USER_ID` in `.env` to your External ID object ID (from `prof users list`). The app refuses it anywhere but local.

App code lives in `src/prof_ai/`. Pushing to `master` deploys automatically (`.github/workflows/deploy.yml`).

## Testing: the shared regression suite

Tests exist mainly so **we don't break each other's work**. Proving your own feature works is a secondary goal.

- Every feature adds tests under `tests/`, in a folder named after the feature slug (e.g. `tests/user_auth/`). Test the public behaviour and contracts other code depends on, such as data shapes, API responses and agent outputs. Don't test internals.
- Tests must be deterministic and run offline. Mock LLM, Azure and network calls, and use fixed seeds for any generated data.
- The whole suite runs with one command: `bash scripts/test.sh`. Run it at the end of every implementation and before every merge.
- **If another person's test fails, assume your change broke it.** Fix your code. Never delete, skip or weaken someone else's test to get green. If you think their test is genuinely wrong, say so in your `handover.md` and leave it for them to decide.
- Keep the suite fast (aim for under 60s) so nobody is tempted to skip it.

## Code style

- Formatters and linters are the source of truth. Run them on every file you touch:
  - Python: `ruff format` + `ruff check --fix` (line length 100).
  - TypeScript/JS: `npm run format` + `npm run lint` + `npm run typecheck` in `web/`. CI fails on any of them.
  - npm dependencies: add as few as possible, pin exact versions (`npm install --save-exact`), commit `package-lock.json`, and use `npm ci` (risk R19). Never use `dangerouslySetInnerHTML` (lint-enforced, R18).
  - CI fails on unformatted or lint-failing Python.
- **Comments: minimal.** Write clear names instead of comments. Comment only *why* something non-obvious is done, never *what* the code does. No commented-out code, no banner comments, no "added for feature X" notes, and no restating of the function name in a docstring. Public interfaces may have a one-line docstring if it adds information.
- Small, focused modules. Match the style of the surrounding code.
- No dead code, unused imports or speculative abstractions. Build what the plan needs.
- An end-of-sprint lint and cleanup pass is planned (tracked in `docs/features/INDEX.md`). Keeping touched files clean now keeps that pass small.

## Secrets and public repo

This repo is **public**. Never commit real student data (names, chats, submissions, photos) anywhere: not in code, fixtures or logs. Use synthetic data only. Never commit keys, connection strings, publish profiles or `.env` files. Use `.env` locally (template in `.env.example`) and app settings or Key Vault in Azure. If a secret is ever committed, rotate it immediately. Removing the commit doesn't make it safe.

## Folder layout

```
docs/
  product/            Vision, architecture and risk register (living drafts)
  features/           One folder per feature: plan.md + handover.md
    INDEX.md          Status table of all features (read first)
    _template/        Copy this for new features
  decisions/          Short architecture decision records (ADRs)
src/prof_ai/          Application code (FastAPI); static/ is the frontend build output (gitignored)
web/                  Frontend (React + TypeScript + Vite); tests are web/src/*.test.ts
tests/                Shared regression suite, one folder per feature
infra/                Bicep (main.bicep + main.bicepparam)
.github/workflows/    CI (lint + tests) and deploy to App Service
data/                 Synthetic data generators and small fixtures (generated output is gitignored)
scripts/              Dev scripts, including test.sh
```
