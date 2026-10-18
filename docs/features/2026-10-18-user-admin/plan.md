# Plan: Users admin page, with email-code invites

- **Owner:** sam
- **Branch:** `sam/user-admin`
- **Date:** 2026-10-18

## Goal
Tutors manage accounts in the web app instead of the CLI: invite, lock, unlock and delete. Admins (Sam, later Punjy) manage everyone. Other tutors manage only their own students. Inviting no longer needs the "Forgot password" step: the invited person signs up with an email code.

Decisions (Sam, 2026-10-18):
- Email-code invites, with no Graph access for the app.
- Admins manage all users; tutors manage only their own students.
- Delete erases the account, chats, usage and profile files.

## Approach
- **Invites replace directory account creation** (ADR 0004, superseding the account part of ADR 0002):
  - `UserAdmin.add` (CLI and web) saves a user record with id `invite-<uuid>` and status `invited`. No External ID account is created.
  - Self-service sign-up is switched **on** in the `prof-ai-email-otp` user flow. Anyone can create an External ID account, but the app's user list is still the gate.
  - On the first signed-in request whose object ID has no record, `current_user` reads the **email claim** from the Easy Auth principal. If an `invited` record has that email, the app replaces it with one keyed by the object ID (`active`) and audits `invite_accepted`. Otherwise the request gets 403 as today.
  - The app registration gets the `email` optional claim on the ID token, so Easy Auth passes it on.
  - A student can't be assigned to a tutor who is still `invited`, so `tutor_id` always points at a real object ID.
- **Admin flag:** `User.is_admin` (default false), set only with the CLI (`prof users set-admin <email> [--revoke]`). `/api/me` returns it.
- **API** (`/api/users`, tutors only; ids in paths, the actor always from sign-in):

  | Method and path | Body | Result |
  |---|---|---|
  | `GET /api/users` | | admins: everyone; tutors: their own students |
  | `POST /api/users` | `{email, display_name, role, tutor_email?}` | 201 with the invited user |
  | `POST /api/users/{id}/lock` | `{reason}` | the locked user |
  | `POST /api/users/{id}/unlock` | `{}` | the unlocked user |
  | `DELETE /api/users/{id}` | | 204 |

  - Non-admins can only invite students, and those students are always assigned to themselves.
  - Nobody can lock or delete themselves through the web.
  - A target you can't manage is a 404, which doesn't reveal that the account exists.
- **Lock from the web is app-side only.** The status is checked on every request, so it takes effect immediately. The CLI still disables the External ID account as well.
- **Delete** (`UserAdmin.remove`) runs in this order, so a failure part-way through can be retried:
  1. Erase conversations and usage (`ChatStore.delete_user_data`) and profile files (`ProfileStore.delete_all`).
  2. Delete the user record.
  3. Delete the External ID account (CLI only).
  4. Audit `user_removed`, with the email in `reason`.

  A tutor who still has students can't be deleted.
- **UI:** a **Users** page at `/users`, linked for tutors:
  - an invite form (admins also choose the role and the tutor) with sign-up instructions after inviting
  - a list with status pills: Invited, Active, Locked
  - Lock (asks for a reason), Unlock, and Delete (confirmation)
- **CLI:**
  - `users add` now creates an invite and prints the sign-up instructions.
  - New `users remove <email>`, which also deletes the External ID account.
  - New `users set-admin <email> [--revoke]`.

## Risks
| Risk | Control |
|------|---------|
| **Open sign-up lets strangers create External ID accounts** (R9) | The app's user list stays the gate: no invited or active record, so 403 on every `/api` call. The shell carries no data. External ID is free up to 50k MAU, so junk accounts cost nothing. |
| **Someone claims another person's invite** | They would have to receive the email code at that address, as with password reset today. The email claim is trusted only from Easy Auth, for our single tenant, and External ID verifies emails at sign-up. Only `invited` records are linked; an `active` record is never re-linked to a new object ID. |
| **The email claim is missing or renamed** | Fail closed: no claim means no link, so 403. Checked live during rollout. |
| **A tutor escalates privilege** (adds a tutor, manages other tutors' students, makes themselves admin) | Server-side checks with tests for each; `is_admin` can't be set through the API at all. |
| **Cross-site request forgery** | Every mutating endpoint needs a JSON body; a `text/plain` or form post gets 422 (tested). `DELETE` is preflighted cross-origin, and no CORS is configured. |
| **Deleting by mistake** (R10) | A confirmation in the UI; the audit trail; Cosmos continuous backup (7 days) and blob soft delete (14 days) allow recovery. You can't delete yourself or a tutor who has students. |
| **Children's data** (R10) | Tutors see only their own students' names and emails. Delete really erases chats, usage and profiles. |
| **A partial failure during delete** | Data first, record last, so a retry finishes the job; 503 with nothing claimed. |
| **Cost** | No model calls. List and delete are cross-partition or per-partition queries, which are small at our scale. |
| **XSS** (R18) | Names and emails render as React text. |

## Files / modules touched
- **Users:**
  - `src/prof_ai/users/models.py`: `INVITED`, `is_admin`
  - `src/prof_ai/users/admin.py`: invites, remove, set_admin, `accept_invite`
  - `src/prof_ai/users/repository.py` and `cosmos_repository.py`: `delete`
  - `src/prof_ai/users/directory.py`: `delete_user`; `create_user` removed
  - `src/prof_ai/users/api.py` (new)
- **Auth:** `src/prof_ai/auth.py`: email claim, invite linking.
- **Chat and profiles:**
  - `src/prof_ai/chat/store.py`, `cosmos_store.py` and `service.py`: delete user data
  - `src/prof_ai/profiles/store.py` and `src/prof_ai/content/store.py` / `azure_backend.py`: blob delete
- **App and CLI:** `src/prof_ai/main.py`, `src/prof_ai/cli.py`.
- **Scripts:** `scripts/setup_external_id.py`: sign-up on, email optional claim.
- **Web:** `web/src/api.ts`, `App.tsx`, `UsersPage.tsx` (new), `styles.css`.
- **Tests:**
  - `tests/user_admin/` (new)
  - `tests/auth/`: Sam's own tests; the add contract changes from "creates a directory account" to "creates an invite"
  - `tests/tutor_chat/conftest.py`: in-memory stores gain delete
- **Docs:**
  - ADR 0004
  - `CLAUDE.md`, `README.md`, `risks.md`, INDEX

## Contracts added or changed
- `User.status` gains `invited`; `User.is_admin: bool`. `/api/me` adds `is_admin`.
- `UserRepository.delete(user_id)`, `ChatStore.delete_user_data(user_id)`, `ProfileStore.delete_all(user_id)`, `BlobBackend.delete(container, name)`, `Directory.delete_user(user_id)`.
- `Directory.create_user` is removed. `UserAdmin.add` returns an `invited` user with id `invite-<uuid>`.
- Audit actions: `invite_accepted`, `user_removed`, `admin_granted`, `admin_revoked`.
- The `/api/users` endpoints above.

## Tests to add
- **Invites:** the first sign-in with a matching email links and activates the invite (case-insensitive, audited). No invite, no email claim, or an active record under another object ID all give 403.
- **Permissions:**
  - admins see and manage everyone
  - tutors see and manage only their own students
  - tutors can't invite tutors
  - students get 403
  - self-lock and self-delete are refused
  - other tutors' students give 404
- **Delete:** erases conversations, usage and profile blobs, then the record, with an audit event. A tutor with students is refused.
- **Lock/unlock:** blocks then restores `/api/me`; a reason is required; locking an invite is refused.
- **Bodies:** non-JSON bodies give 422.
- **CLI:** `remove` and `set-admin`.
- **Web client:** list, invite, lock, delete (204, no body).

## Open questions
- Invites don't expire. Add an expiry if stale invites become a problem.
- Should admins edit display names or move a student to another tutor? Not in this cut.
