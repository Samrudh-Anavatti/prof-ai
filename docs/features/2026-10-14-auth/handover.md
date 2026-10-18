# Handover: Auth (invite-only sign-in, users and account locks)

- **Owner:** sam
- **PR:** https://github.com/Samrudh-Anavatti/prof-ai/pull/5
- **Merged:** 2026-10-18

## What was built
- **External ID tenant** `profai.onmicrosoft.com` (`c01293ab-8f78-46af-aa73-1c8fd5a88555`), created by `scripts/create-external-tenant.sh`. Sam is Global Administrator.
- **App registration** "Prof AI web" (client ID `e79af39b-5c6d-4f3d-90bd-895875d8af11`): redirect URI `https://prof-ai.azurewebsites.net/.auth/login/aad/callback`, ID-token issuance on (needed for Easy Auth's hybrid flow), admin consent for `openid profile email offline_access`. Created by `scripts/setup_external_id.py` (idempotent).
- **User flow** `prof-ai-email-otp` (ID `e63f958c-3bd7-4396-8f03-9bbc08660ff7`): **sign-up disabled**, linked to the app.
- **App Service Authentication** (`authsettingsV2` in Bicep):
  - Every path requires sign-in except `/healthz`. Browsers are redirected to sign-in; non-browser clients get 401.
  - Token store off.
  - The client secret comes from Key Vault through the `AUTH_CLIENT_SECRET` app setting.
- **Key Vault** `kv-prof-ai-cjzzqh`: RBAC mode, purge protection on.
  - The web app has *Secrets User*; tutors have *Secrets Officer*.
  - Secret `auth-client-secret` expires **2027-04-16**. Rotate with `.venv/Scripts/python scripts/rotate_auth_secret.py`.
- **Cosmos DB serverless** `cosmos-prof-ai`: database `prof-ai`, containers `users` (pk `/id`) and `audit` (pk `/user_id`). Local auth is off; the web app and tutors have *Built-in Data Contributor*.
- **App code:**
  - `prof_ai.auth`: `CurrentUser` / `require_role` dependencies and Easy Auth principal parsing.
  - `prof_ai.users`: models, repository protocol, Cosmos repository, the External ID directory over Graph, and `UserAdmin`.
  - `prof_ai.graph`: a minimal Graph client.
  - `GET /me` (now `GET /api/me`).
- **CLI:** `prof users add | list | lock | unlock`.
- **Verified live on 2026-10-18:** Sam signed in at https://prof-ai.azurewebsites.net/me and got his tutor record. Unauthenticated requests and requests with a spoofed principal header both get 401.

**Differences from the plan:**
1. **Easy Auth's client credential is a Key Vault secret, not a managed identity federated credential.** Entra accepted the cross-tenant FIC, but code redemption failed at runtime. The FIC and its identity are deleted.
2. **User flow creation needed the portal.** The Azure CLI's Graph token can't read identity providers or change authentication-method policies, so Sam enabled Email OTP and created the flow in the portal. The script then disabled sign-up and linked the app.
3. **Users sign in with email + password, not email codes.** Accounts created through Graph must have a password, so External ID asks for it. The first sign-in uses "forgot password" to set one. See open decision below.
4. **The provider ID is `EmailOtpSignup-OAUTH`** (not `-OAUTH2` as some docs say).

## How to run / use it
- **Invite someone:**
  ```bash
  prof users add --email x@example.com --name Alex --role student --tutor samrudh.anavatti@gmail.com
  ```
  They go to https://prof-ai.azurewebsites.net, enter their email, choose "forgot password", get a code by email and set a password.
- **Lock or unlock:** `prof users lock <email> --reason "..."` / `prof users unlock <email>`.
- **Local dev without sign-in:** `DEV_USER_ID=<object id>` in `.env`, then run uvicorn. It's refused outside `APP_ENV=local` and on App Service.
- **Debugging sign-in:** read the External ID sign-in logs, which show the real AADSTS error. With the Azure CLI's token, query `https://graph.microsoft.com/beta/auditLogs/signIns` in the External ID tenant. App Service's Linux auth sidecar doesn't surface its own logs.
- **Gotcha (Git Bash):** set `MSYS_NO_PATHCONV=1` for `az` commands that take `/subscriptions/...` arguments, or Git Bash rewrites them into Windows paths.

## Contracts other code can rely on
- **Every new endpoint depends on `CurrentUser` or `require_role(Role.TUTOR)` / `require_role(Role.STUDENT)`.** Never read identity headers directly.
- **`User`** (`src/prof_ai/users/models.py`):
  - `id` (External ID object ID, also the Cosmos id and partition key), `email` (lowercase), `display_name`
  - `role` (`tutor` | `student`), `status` (`active` | `account_locked`)
  - `tutor_id` (students only), `created_at`, `updated_at`
- **`AuditEvent`:** `id`, `user_id`, `action` (`user_added` | `account_locked` | `account_unlocked`), `actor`, `reason`, `at`.
- **`GET /me`** returns `{id, email, display_name, role, status}`. Since the frontend skeleton (2026-10-18) this is **`GET /api/me`**.
- **Failure modes:** a missing or invalid principal gets 401; uninvited or locked accounts get 403; a store that's down or not configured gets 503.
- **App settings:** `COSMOS_ENDPOINT`, `EXTERNAL_TENANT_ID`, `AUTH_CLIENT_SECRET` (Key Vault reference). App Service sets `WEBSITE_AUTH_ENABLED`.

## Tests added
`tests/auth/` (25 tests):
- principal parsing
- `/me` shape
- 401 when not signed in, and when platform auth is off in production
- 403 for uninvited or locked accounts; 503 when the store fails
- `/healthz` open
- dev-user guard
- `UserAdmin` add / validate / duplicate / tutor linking / resume after an interrupted add / lock and unlock in both stores with audit
- CLI `users` commands

## Known issues / TODOs
- **Open decision (Sam):** keep email + password (A), or move to passwordless (B): self-service email-code sign-up plus the app allowlist. Under B, `prof users add` would create a pending invite keyed by email, and the first sign-in would link the object ID.
- **Session lifetime** is Easy Auth's default (8 hours). Decide whether students get shorter sessions.
- **No anomaly detection yet** (R9).
- **Not automated in Bicep:** the External ID tenant and the portal steps (Email OTP, user flow) are one-off; see the scripts.
- **Postgres → Cosmos:** later features needing relational reporting should design their Cosmos containers deliberately (partition by student).

## For the other dev
Once you're in the workforce tenant and in `tutorPrincipalIds`, Sam needs to add you as a tutor (`prof users add --role tutor`) so you can sign in to the app. Admin work in the External ID tenant (Graph through the CLI) also needs a role there, so Sam should make you an admin of `profai.onmicrosoft.com` too.
