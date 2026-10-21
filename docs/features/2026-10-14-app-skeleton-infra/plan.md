# Plan: App skeleton and Azure infrastructure

- **Owner:** sam
- **Branch:** `sam/app-skeleton-infra`
- **Date:** 2026-10-14

## Goal
A deployed, empty Prof AI app at its default `azurewebsites.net` domain, with the core Azure infrastructure defined in Bicep and CI/CD in place, so later features (auth, content store, chat) have somewhere to land.

## Approach
- **Stack ADR (`docs/decisions/0001-stack.md`):** Python 3.11 + FastAPI on App Service Linux B1, matching our other projects. The frontend framework is deferred until a feature needs real UI.
- **App:** a FastAPI package under `src/prof_ai/` with `/healthz` and a placeholder landing page. API docs are disabled in production. Started with `startup.sh` (uvicorn).
- **Infra (`infra/main.bicep`), all in `rg-prof-ai`, UK South, tagged `project=prof-ai`, `owner=sam`:**
  - Log Analytics (30-day retention, daily ingestion cap) + workspace-based App Insights.
  - Storage account: no public blob access, **shared-key auth disabled** (Entra only), TLS 1.2. Containers `sources`, `content` and `answer-keys`, created empty now for the content store.
  - Foundry: an AIServices account with **local (key) auth disabled**, a project, and a `gpt-5.6-luna` deployment at low capacity. Content Safety uses the same account.
  - App Service plan B1 Linux + web app: system-assigned identity, HTTPS only, FTP and basic-auth publishing disabled, health check on `/healthz`.
  - RBAC with least privilege:
    - The web app gets *Cognitive Services OpenAI User* on Foundry, and *Storage Blob Data Reader* on the `content` container only.
    - Tutors get *Storage Blob Data Contributor* on the account and *OpenAI User* on Foundry, for the CLI and local dev.
  - Deploy identity: a user-assigned managed identity with a GitHub OIDC federated credential (master branch only) and *Website Contributor* on the web app. No publish profile, no secrets.
  - Monthly cost budget with email alerts (moved from the manual setup into Bicep).
- **Resource group:** recreate `rg-prof-ai` in UK South (it's empty; it was created in eastus2).
- **Scripts:** `scripts/deploy-infra.sh` (what-if + deploy), and `scripts/test.sh` uses `.venv` when present.
- **CI:** `.github/workflows/ci.yml` (ruff + tests on PRs and pushes) and `deploy.yml` (on master: tests, then OIDC login and deploy).

## Risks
- **Cost:** B1 is about £10/month. Log Analytics has a daily cap. Foundry is pay per token, and the low deployment capacity rate-limits worst-case spend. The budget alert stays on.
- **Secrets / public repo:** no keys exist. Everything authenticates with managed identity or OIDC, shared-key auth is off on storage and local auth is off on Foundry, so there's nothing to leak.
- **Data residency:** the app and data are in UK South. GlobalStandard model deployments may process prompts outside the UK. That's acceptable while there's no real student data; revisit before real students (added to the risk register as R16).
- **Exposure:** the app is public, but it only serves a health check and a placeholder until auth lands. API docs are off in production.
- **Deploy hijack:** the OIDC credential is limited to this repo's `master` branch, and its role is limited to the one web app.

## Files / modules touched
- `src/prof_ai/`, `startup.sh`, `requirements*.txt`, `pyproject.toml`
- `infra/main.bicep`, `infra/main.bicepparam`, `scripts/deploy-infra.sh`, `scripts/test.sh`
- `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
- `docs/decisions/0001-stack.md`, `docs/product/risks.md`, `CLAUDE.md`, `.env.example`

## Contracts added or changed
- `GET /healthz` returns `200 {"status": "ok"}`. App Service health checks and deploy smoke checks rely on it.
- App settings / env vars: `APP_ENV`, `FOUNDRY_ENDPOINT`, `CHAT_DEPLOYMENT`, `STORAGE_ACCOUNT_URL`, `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Blob containers: `sources`, `content`, `answer-keys` (the layout inside them comes with the content-store feature).

## Tests to add
`tests/app_skeleton/`: the health check contract, the landing page returning HTML, and API docs disabled when `APP_ENV=production`.

## Open questions
- Punji's Entra object ID (and whether they're in the same tenant), to add them to `tutorPrincipalIds`.
