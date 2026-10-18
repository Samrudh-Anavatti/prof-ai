# Plan: Auth (invite-only sign-in, users and account locks)

- **Owner:** sam
- **Branch:** `sam/auth`
- **Date:** 2026-10-14

## Goal
Only people a tutor has invited can reach the app. Every request knows who the user is and their role (tutor or student). A tutor can lock an account instantly. This is the foundation for assignments, chat and tutor review.

## Decisions (Sam, 2026-10-14)
- **Identity provider: a dedicated Microsoft Entra External ID tenant** (free at our scale). Students are isolated from the workforce tenant that controls the Azure subscription.
- **Sign-in with email one-time passcodes. No passwords.** Invite-only: sign-up is disabled in the user flow.
- **App database: Cosmos DB serverless** (pay per request), with Entra-only data-plane auth.

## Approach
- **Infra (Bicep):**
  - Cosmos DB account: serverless, `disableLocalAuth: true`. Database `prof-ai` with containers `users` (pk `/id`) and `audit` (pk `/user_id`).
  - Data-plane role *Cosmos DB Built-in Data Contributor* for the web app identity and the tutors.
  - App Service Authentication ("Easy Auth") pointing at the External ID tenant. Every path requires sign-in except `/healthz`, and unauthenticated users are redirected to sign-in.
  - Where possible, the Easy Auth client credential is a user-assigned managed identity used as a federated credential (no secret). If cross-tenant FIC doesn't work, fall back to a client secret in Key Vault.
- **External ID setup:**
  1. Create the tenant (ARM `Microsoft.AzureActiveDirectory/ciamDirectories`).
  2. Create an app registration for the web app.
  3. Create an email-OTP user flow with sign-up disabled, linked to the app.

  Graph calls into the new tenant need Sam's interactive `az login --tenant`. These steps are scripted where possible and the manual ones documented.
- **App:**
  - `prof_ai.auth`: reads the `X-MS-CLIENT-PRINCIPAL` header that Easy Auth injects (App Service strips client-sent copies) and resolves the user by External ID object ID in `users`.
  - Unknown users get 403 ("not invited"), and so do locked accounts.
  - A local dev mode (`APP_ENV=local`, `DEV_USER_ID`) acts as a given user. It refuses to run on App Service.
  - `GET /me` returns the current user. The landing page greets the user and links to sign out.
- **Users and audit:**
  - `prof_ai.users`: `User` model (id = External ID object ID, email, display name, role, status, tutor ID, timestamps), a repository protocol (Cosmos and in-memory), and audit events.
  - `UserAdmin` service: add, list, lock and unlock.
    - **Add** creates the External ID account through Microsoft Graph, then the `users` document.
    - **Lock** sets `status=account_locked` *and* disables the account in External ID. **Unlock** reverses both.
    - Every action writes an audit event.
- **CLI:** `prof users add | list | lock | unlock`. It runs as the tutor (`az login`), and Graph calls use Sam's identity in the External ID tenant.

## Risks
- **Unauthorised access (R9):**
  - Sign-up is disabled at the IdP, and the app allowlist is a second, independent check: an authenticated identity with no `users` document gets 403.
  - No passwords exist to phish or share. Email OTP proves the student owns the inbox.
- **Header spoofing:** the app only trusts `X-MS-CLIENT-PRINCIPAL` in production behind Easy Auth, which strips client-supplied copies. Local dev mode refuses to start when `WEBSITE_SITE_NAME` is set (i.e. on App Service).
- **Locked user keeps access:** the lock is checked on every request (no caching), and the account is disabled at the IdP so no new sessions start. Existing Easy Auth sessions are still rejected by the per-request status check.
- **Cross-tenant blast radius:** student identities live in the External ID tenant and have no Azure RBAC anywhere.
- **Children's data (R10):** store only email, display name (first name is enough), role and status. No real student data in tests; fixtures are synthetic.
- **Secrets:** aim for zero via the managed-identity federated credential. If a secret is unavoidable, it goes in Key Vault with a Key Vault reference, never in the repo or plain app settings.
- **Cost:** Cosmos serverless and External ID are effectively £0 at our scale.
- **Failure:** if Cosmos is unavailable, requests needing a user fail with 503 (fail closed), never as anonymous access.

## Files / modules touched
- `infra/main.bicep`, `infra/main.bicepparam`
- `src/prof_ai/auth.py`, `src/prof_ai/users/` (`models.py`, `repository.py`, `cosmos_repository.py`, `directory.py`, `admin.py`), `src/prof_ai/main.py`, `src/prof_ai/config.py`, `src/prof_ai/cli.py`
- `scripts/` (External ID setup helpers), `CLAUDE.md`, `.env.example`, `docs/product/risks.md`

## Contracts added or changed
- `User` document shape in `users`, and `AuditEvent` in `audit`.
- `prof_ai.auth.current_user` FastAPI dependency (+ `require_role`). Every later endpoint uses it.
- `GET /me` returns `{id, email, display_name, role, status}`.
- Env vars: `COSMOS_ENDPOINT`, `EXTERNAL_TENANT_ID`, `DEV_USER_ID` (local only).

## Tests to add
`tests/auth/`:
- principal header parsing
- unknown user → 403
- locked user → 403
- missing principal in production → 401
- `/healthz` reachable unauthenticated
- `/me` shape
- local dev mode works locally and refuses on App Service
- `UserAdmin`:
  - add creates the directory account and the user
  - duplicate email refused
  - a student needs an existing tutor
  - lock/unlock flips both store and directory and writes audit events
- CLI `users` commands against fakes

## Open questions
- Do grade 6 students have their own email, or do we use a parent's? With OTP, whoever owns the inbox can sign in.
- Session lifetime: Easy Auth defaults to 8 hours. Shorter for students?
