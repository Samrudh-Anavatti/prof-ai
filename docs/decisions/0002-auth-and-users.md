# 0002: Sign-in, users and the app database

- **Status:** accepted (2026-10-14, Sam)

## Context
Students are children aged 11–18. Only invited people may use the app, and a tutor must be able to lock an account instantly. We also need an app database for users now and for assignments, chats and marks later.

## Decision
- **Identity:** a dedicated **Entra External ID** tenant, `profai.onmicrosoft.com` (tenant `c01293ab-8f78-46af-aa73-1c8fd5a88555`). It's separate from the workforce tenant that controls the Azure subscription, so student identities have no reach into Azure.
- **Sign-in:** **App Service Authentication** ("Easy Auth") against that tenant.
  - It covers every path except `/healthz`.
  - The app trusts the `X-MS-CLIENT-PRINCIPAL` header only when `WEBSITE_AUTH_ENABLED` is true.
  - The user flow `prof-ai-email-otp` has **sign-up disabled**; accounts are created by tutors with `prof users add`.
- **Authorisation:**
  - The app's own `users` container is the source of truth for role and status.
  - An authenticated identity without a user document gets 403.
  - Locks are checked on every request and also disable the account in External ID.
- **Database:** **Cosmos DB serverless** (`cosmos-prof-ai`) with Entra-only data-plane auth. Chosen by Sam over Postgres B1ms on cost (about £0 vs about £12/month).
- **Easy Auth client credential:** a **client secret in Key Vault** (`kv-prof-ai-cjzzqh`), read through a Key Vault reference by the app's system identity. It has a 180-day lifetime and is rotated by `scripts/rotate_auth_secret.py`.

## Alternatives considered
- **Students as B2B guests in the workforce tenant:** rejected. It puts children in the directory that controls the subscription.
- **Postgres Flexible Server:** better for relational reporting, but a fixed monthly cost. Revisit if reporting queries get painful.
- **Managed identity as a federated credential (no secret):** tried first. Entra accepted the configuration, but code redemption failed at runtime with the app registration in the External ID tenant and the identity in the workforce tenant. Replaced by the Key Vault secret.

## Consequences
- **One secret exists.** It must be rotated before it expires (the current one expires on 2027-04-16).
- **Admin tasks reach Graph through the Azure CLI's token.** That token can create users and app registrations but can't change authentication-method policies or read identity providers. Those needed the portal (see the auth handover).
- **Accounts created through Graph always have a password**, so users currently sign in with email + password (first time via "forgot password"). Whether to move to truly passwordless (self-service email-code sign-up plus the app allowlist) is an open decision for Sam.
