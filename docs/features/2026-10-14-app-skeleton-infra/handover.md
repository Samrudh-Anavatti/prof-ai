# Handover: App skeleton and Azure infrastructure

- **Owner:** sam
- **PR:** https://github.com/Samrudh-Anavatti/prof-ai/pull/2
- **Merged:** 2026-10-14

## What was built
- **App:** a FastAPI app in `src/prof_ai/`. It serves `/healthz`, a placeholder landing page at `/`, and API docs (`/docs`) only outside production. `create_app(settings)` is the factory, and `config.load_settings()` reads env vars.
- **Infra:** everything is in `infra/main.bicep`, in `rg-prof-ai`, UK South:

  | Resource | Name | Notes |
  |----------|------|-------|
  | App Service plan + web app | `plan-prof-ai` (B1 Linux), `prof-ai` | https://prof-ai.azurewebsites.net; system identity; HTTPS only; FTP and basic-auth publishing off; health check `/healthz` |
  | Foundry | `foundry-prof-ai` + project `prof-ai` | Key auth disabled; deployment `gpt-5.6-luna` (GlobalStandard, capacity 10 = 10k tokens/min); default content filter `Microsoft.DefaultV2` |
  | Storage | `stprofaicjzzqh` | Shared-key auth off, no public access; containers `sources`, `content`, `answer-keys`; 14-day soft delete |
  | Monitoring | `log-prof-ai`, `appi-prof-ai` | 30-day retention, 0.5 GB/day cap |
  | Deploy identity | `id-prof-ai-deploy` | GitHub OIDC for `master` of this repo only; Website Contributor on the web app only |
  | Budget | `prof-ai-monthly` | £50/month; alerts at 50% and 90% actual and 100% forecast |

- **RBAC:**
  - The web app can call Foundry (*Cognitive Services OpenAI User*) and read the `content` container only.
  - Tutors in `tutorPrincipalIds` can read and write all blobs and call Foundry.
- **CI/CD:**
  - `ci.yml` runs `ruff format --check`, `ruff check` and `scripts/test.sh` on PRs and on `master`.
  - `deploy.yml` deploys `master` (tests → OIDC login → zip deploy with an Oryx build → smoke check on `/healthz`).
  - Repo variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_WEBAPP_NAME`.

**Differences from the plan:**
- **No Key Vault.** No secrets exist, so it would be unused. Add it when the first secret appears.
- **Postgres** comes with the auth feature.
- **The first infra deploy failed** because Foundry rejects concurrent changes to one account. Fixed with `dependsOn: [foundryProject]` on the model deployment.
- **GitHub OIDC subjects now include immutable IDs:** `repo:Samrudh-Anavatti@95168210/prof-ai@1408891815:ref:refs/heads/master`, not `repo:Samrudh-Anavatti/prof-ai:...`. The first deploy run failed with AADSTS700213 until `githubRepo` in `main.bicep` used that form. Get the IDs with `gh api repos/<owner>/<repo> --jq '"\(.owner.login)@\(.owner.id)/\(.name)@\(.id)"'`.

## How to run / use it
- **Local:** see "Local setup and commands" in `CLAUDE.md`.
- **Infra:** `bash scripts/deploy-infra.sh --what-if`, then without the flag. It needs `BUDGET_CONTACT_EMAILS` in `.env`, which keeps the email out of the public repo. Works from Git Bash on Windows (falls back to `az.cmd`).
- **Calling the model locally:** `az login`, then use an Entra token for `https://cognitiveservices.azure.com` against `https://foundry-prof-ai.cognitiveservices.azure.com/openai/v1/` (Responses API). There are no API keys. Verified working on 2026-10-14.

## Contracts other code can rely on
- `GET /healthz` returns `200 {"status": "ok"}`. Used by the App Service health check and the deploy smoke check.
- App settings in production: `APP_ENV=production`, `FOUNDRY_ENDPOINT`, `CHAT_DEPLOYMENT`, `STORAGE_ACCOUNT_URL`, `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Deploy package = `src/`, `requirements.txt`, `startup.sh`. Runtime dependencies go in `requirements.txt`; dev/test-only ones go in `requirements-dev.txt`.

## Tests added
`tests/app_skeleton/test_app.py`: the health check contract, the landing page returning HTML, docs disabled in production, docs available locally.

## Known issues / TODOs
- **Model processing location (R16):** GlobalStandard may process prompts outside the UK. Revisit before real students.
- **Content filters:** the default filter is moderate. The chat feature should add a custom, stricter filter for a grade 6–12 audience.
- **Punjy's access:** he isn't in the tenant yet. Once he is, add his object ID to `tutorPrincipalIds` in `infra/main.bicepparam` and redeploy the infra.
- **Bicep CLI:** 0.36 works, but `az bicep upgrade` is available.

## For the other dev
You need tenant access first (Sam is adding you). After that, `az login` gives you Foundry and blob access through `tutorPrincipalIds`. Never add API keys or connection strings; use `DefaultAzureCredential`.
