# 0001: Stack and hosting

- **Status:** accepted (2026-10-14)
- **Decided by:** Sam

## Context
We need something deployed quickly, cheaply and safely, with existing Azure quota for App Service and Foundry. Sam's other projects (football-betting, TT-App) already run FastAPI on App Service B1, so the team knows that path.

## Decision
- **Backend:** Python 3.11 + FastAPI, served by uvicorn on **App Service Linux B1** in **UK South**. The web app is `prof-ai` at the default domain `https://prof-ai.azurewebsites.net`.
- **AI:** a **Microsoft Foundry** AIServices account (`foundry-prof-ai`) with a project. The default chat model is `gpt-5.6-luna` (GlobalStandard), which also served the same cheap-but-capable role in football-betting. Content Safety runs on the same account.
- **Storage:** one Storage account with containers `sources`, `content` and `answer-keys` (see `docs/product/architecture.md`).
- **Identity between services:** managed identity only. Key auth is disabled on Foundry, shared-key auth is disabled on Storage, and GitHub deploys use OIDC to a user-assigned identity. The repo is public and we hold no keys.
- **IaC:** Bicep in `infra/main.bicep`, applied by `scripts/deploy-infra.sh`.
- **CI/CD:** GitHub Actions. `ci.yml` runs ruff and the tests. `deploy.yml` deploys `master` to App Service.
- **Frontend:** not decided. The app serves a placeholder page; choose when the first real UI feature is planned.

## Alternatives considered
- **Container Apps / AKS:** more flexible, but more moving parts and cost than an empty app needs. Revisit if we need background workers at scale.
- **API keys and a publish profile** (as in our earlier projects): simpler, but they're long-lived secrets next to a public repo.
- **SQLite on App Service `/home`** (as in football-betting): cheap, but `/home` is a network share. It caused the 2026-10-12 football-betting outage. The database choice comes with the auth feature.

## Consequences
- **Cost:** about £10/month fixed (B1), plus pay-per-token model usage. Low deployment capacity (10k tokens/min) caps worst-case spend.
- **No keys for local dev:** developers run `az login` and use their Entra identity, which needs tutor roles in `tutorPrincipalIds`.
- **Data residency:** GlobalStandard may process prompts outside the UK. That's fine for development with synthetic data, and must be revisited before real students (risk R16).
