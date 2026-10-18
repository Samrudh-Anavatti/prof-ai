# 0004: Email invites with self-service sign-up

- **Status:** accepted (2026-10-18, Sam). Supersedes the account-creation part of [ADR 0002](0002-auth-and-users.md).

## Context
Under ADR 0002, `prof users add` created each External ID account through Microsoft Graph. Graph requires a password on such accounts, so every new user had to go through "Forgot password" on their first sign-in. We now want tutors to invite people from the web app. Giving the web app Graph rights (`User.ReadWrite.All`) in the student tenant would put full account control behind the app's secret.

## Decision
- **Self-service sign-up is on** in the `prof-ai-email-otp` user flow. Anyone can create an External ID account with an email code.
- **The app's `users` container stays the gate.**
  - Inviting someone saves a user record with status `invited`, keyed `invite-<uuid>`.
  - On the first signed-in request whose object ID has no record, the app reads the **email claim** that Easy Auth passes on. If an `invited` record has that email, the app re-keys it to the object ID and activates it.
  - Everyone else gets 403, as before.
- **The app registration emits the `email` optional claim** in the ID token (`scripts/setup_external_id.py`).
- **The web app never calls Graph.**
  - Locks from the web are app-side: the status is checked on every request.
  - The CLI, using a tutor's `az login`, still disables or deletes the directory account as well.
- **Admins** (`User.is_admin`, set only with the CLI) manage all users in the web app. Other tutors manage only their own students.

## Alternatives considered
- **Grant the "Prof AI web" registration Graph `User.ReadWrite.All` and reuse its Key Vault secret.** This keeps the password flow and the first-sign-in reset. A leaked secret would control every student-tenant account. Rejected.
- **A separate admin app registration with its own secret.** It has the same blast radius as the first alternative, plus a second secret to rotate. Rejected.

## Consequences
- **Junk accounts.** Strangers can create External ID accounts, but they get no data, and the tenant is free up to 50k monthly active users. Delete junk accounts in the portal if they pile up.
- **Linking relies on the email claim.** The issuer is fixed to our tenant, and External ID verifies the email with a code at sign-up. If the claim is ever missing, linking fails closed (403).
- **Sign-in is passwordless for new users** (an email code each time). Accounts created under ADR 0002 keep their passwords.
- **Deleting someone in the web app doesn't delete their External ID account.** The leftover account can sign in but gets 403. `prof users remove` deletes both.
