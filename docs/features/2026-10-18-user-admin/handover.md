# Handover: Users admin page with email-code invites

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-18

## What was built
- **Users page** at `/users`, in the top bar for tutors (Chat · Teaching style · Users):
  - **Invite**: email and first name. Admins also pick the role and, for students, the tutor. After inviting, the page shows the sign-up instructions to pass on.
  - **The list** shows status pills (Invited, Active, Locked), with Lock (asks for a reason), Unlock and Delete (confirmation).
  - **What you see:**
    - Admins see everyone, with each student's tutor.
    - Other tutors see themselves and their own students.
    - Your own row has no actions.
- **Invites** ([ADR 0004](../../decisions/0004-invites-and-sign-up.md)):
  - Adding a user, in the web or the CLI, saves an `invited` record (`invite-<uuid>`). No directory account is created.
  - The invitee signs up at the site with an email code. Their first request links the invite through the email claim and audits `invite_accepted`.
- **Delete** erases conversations, usage, `profile.md` and `teaching-style.md`, then the user record, and audits `user_removed`. The CLI also deletes the External ID account. A tutor who still has students can't be deleted.
- **Admins:** `User.is_admin`, which `/api/me` returns. It is set only with `prof users set-admin <email> [--revoke]`.
- **CLI:**
  - `users add` now invites and prints the sign-up instructions.
  - New `users remove` and `users set-admin`.
  - `users list` shows an `admin` column.
- **Setup script** (`scripts/setup_external_id.py`) now turns sign-up **on** and adds the `email` optional claim to the ID token.

**Differences from the plan:**
- Tutors' lists include themselves, marked "You".
- An admin inviting a student without choosing a tutor becomes that student's tutor.
- `unlock` now refuses an account that isn't locked.
- `Directory.find_user_id` and `create_user` were removed (unused under invites), along with the `EXTERNAL_TENANT_DOMAIN` setting.

## How to run / use it (rollout, in this order)
1. **Merge** (this deploys the app).
2. **Configure the tenant:** `.venv/Scripts/python scripts/setup_external_id.py`. This turns on sign-up and adds the email claim; it's idempotent.
3. **Make yourself admin:** `.venv/Scripts/prof users set-admin samrudh.anavatti@gmail.com`.
4. **Test with an email you can read:** invite it on `/users`, then sign up in a private window. It should land in the chat, and show as Active on `/users`.
   - If it gets "This account hasn't been invited", the email claim isn't arriving. Check the External ID sign-in logs and the app registration's token configuration.

## Contracts other code can rely on
- **Users API** (tutors only; non-admins act only on their own students; you can't act on yourself):

  | Method and path | Body | Result |
  |---|---|---|
  | `GET /api/users` | | `[{id, email, display_name, role, status, is_admin, tutor_email, created_at}]` |
  | `POST /api/users` | `{email, display_name, role?, tutor_email?}` | 201 |
  | `POST /api/users/{id}/lock` | `{reason}` | the user |
  | `POST /api/users/{id}/unlock` | `{}` | the user |
  | `DELETE /api/users/{id}` | | 204 |

  Errors:
  - 400 `{detail}` for validation;
  - 403 for students, for non-admins inviting tutors, and for acting on yourself;
  - 404 for users you can't manage;
  - 422 for a non-JSON body;
  - 503 if a store is down or not configured.
- **`/api/me`** adds `is_admin`.
- **`User.status`** can be `invited`. **Invited records must never authenticate** (`current_user` refuses them).
- **Store methods:**
  - `UserRepository.delete`, `ChatStore.delete_user_data`, `ChatService.erase_user_data`
  - `ProfileStore.delete_all`, `BlobBackend.delete`
  - `Directory` is now `set_enabled` + `delete_user`
- **`UserAdmin(repository, directory | None, actor, erase_user_data, clock)`.** Pass `None` for the directory in the web app.
- **`app.state.erase_user_data`** is `None` unless both the chat service and the profile store are configured; delete then returns 503. **New per-user data must be erased here too.**
- **Audit actions:** `invite_accepted`, `user_removed` (the email is in `reason`), `admin_granted`, `admin_revoked`.

## Tests added
- **`tests/user_admin/`** (24 tests):
  - visibility for admins and tutors; student 403
  - invite rules; invalid invites
  - invite acceptance: case-insensitive, no match gives 403, an active record is never re-linked, an invite id can't sign in
  - lock and unlock round trip; reason and invited checks
  - cross-tutor 404s; no acting on yourself
  - delete erases everything and leaves others' data; a tutor with students is refused; a failure keeps the account
  - non-JSON bodies give 422; no stores gives 503
- **`tests/auth/`** (Sam's): `UserAdmin` tests updated from "creates a directory account" to the invite contract, plus remove, set-admin and the CLI. `/api/me` now includes `is_admin`.
- **`web/src/api.test.ts`:** invite, lock (with path encoding), a 204 delete, and delete refusals.

## Known issues / TODOs
- **Not verified in a browser** or against the live tenant yet; see the rollout steps. The email claim's name in Easy Auth's principal is handled for both `email` and the `…/emailaddress` URI.
- **Invites don't expire.**
- **Web deletes leave the External ID account in place** (it gets 403). Use `prof users remove` for a full purge.
- **There's no web UI to rename users or move a student to another tutor.**
- **Accounts created before this change** (Sam, Hchin) keep email + password sign-in.

## For the other dev
Ask Sam to invite you as a tutor at `/users` and to make you an admin (`prof users set-admin`) if you should manage everyone. You'll sign up with an email code; no password is needed.
