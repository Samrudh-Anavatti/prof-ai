# Handover: Teaching style editor in the web UI, plus README overhaul

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-18

## What was built
- **Teaching style page** at `/teaching-style`, linked from the top bar for tutors only:
  - a Markdown editor for the tutor's own `profiles/<tutor-id>/teaching-style.md`, with a live byte count against 8 KB and an unsaved-changes warning
  - **Save**, and **Save and try it**, which saves and opens a fresh chat so the effect is visible straight away
  - **What Luna is told**: the assembled system prompt (base → style → the tutor's own profile) as plain text
- **API:** `GET` and `PUT /api/teaching-style`, tutors only. Each save writes an audit event.
- **Wiring:** `create_app` builds one `ProfileStore` that the chat service and the new router share.
- **Infra:** the web app's role on the `profiles` container changed from Storage Blob Data Reader to **Contributor**, still scoped to that container only.
- **README:** rewritten as the front page, with status, a 🆕 Latest section, a Mermaid Azure diagram, a service table, an access matrix, a chat sequence diagram, decisions and direction, open items, links (app, GitHub, every Azure resource) and a CLI cheat sheet.
- **CLAUDE.md:** a new rule that whoever merges updates the README's Latest section; the CLI is run from the venv; uvicorn now gets `--env-file .env`.

**Differences from the plan:**
- `ChatPage.tsx` didn't need changing: navigating back to chat remounts it with a new, empty chat.
- **Local-run fix:** the app never loaded `.env` by itself (only the CLI did), so the documented `uvicorn` command now passes `--env-file .env`.

## How to run / use it
1. **Deploy the infra** (`bash scripts/deploy-infra.sh --what-if`, then without the flag). Without this, saving on prod fails with 503, because the app can only read `profiles`. Reading works either way.
2. **Remove the old reader assignment** afterwards. Bicep doesn't delete it, and it's harmless but stale:
   ```bash
   az role assignment delete --assignee <app principal id> --role "Storage Blob Data Reader" \
     --scope <storage account id>/blobServices/default/containers/profiles
   ```
3. Sign in as a tutor, click **Teaching style**, edit, then **Save and try it**.

## Contracts other code can rely on
- `GET /api/teaching-style` → `{content, system_prompt, max_bytes}`. `content` is `""` if the tutor has no style.
- `PUT /api/teaching-style` `{content}` → the same shape after saving:
  - 400 `{detail}` for an empty or oversized style;
  - 403 for non-tutors;
  - 422 for a non-JSON body;
  - 503 if Blob is down or not configured.
- Audit event `action="teaching_style_updated"`, `user_id` = the tutor, `actor` = the tutor's email.
- `create_app(..., profile_store: ProfileStore | None = None)`. `app.state.profile_store` may be `None` (endpoints return 503).
- **README:** the "🆕 Latest" section is updated on every merge (see CLAUDE.md).

## Tests added
- **`tests/teaching_style_editor/`** (13 tests):
  - empty style and base prompt
  - save and read back
  - the save lands in the tutor's own blob and changes only that tutor's students' chats
  - students get 403 on GET and PUT
  - signed out gets 401
  - empty and oversized styles get 400
  - a `text/plain` body gets 422 (the CSRF guard)
  - audit events
  - a blob failure gets 503 and is not audited
  - no store gets 503
- **`web/src/api.test.ts`:** `saveTeachingStyle` sends a PUT with JSON and surfaces a 400 detail.

## Known issues / TODOs
- **Last write wins.** Two tabs editing the same style overwrite each other. That's fine for one tutor.
- **No style history in the app.** With versioning off, blob soft delete still keeps each overwritten version as a soft-deleted snapshot for 14 days, recoverable in the portal. Audit events record when a save happened, not what changed.
- **The prompt preview shows the tutor's own view.** Their students see the same, with the student's profile in place of the tutor's.
- **Not verified in a browser.** The UI built, linted and type-checked, and the API was checked locally against the real blob (read only). Click through it once after deploy.
- **The Mermaid diagrams** in the README use standard syntax, but check that GitHub renders them on the PR.

## For the other dev
- Once you have a tutor account, edit your style at https://prof-ai.azurewebsites.net/teaching-style and use **Save and try it** to compare with Sam's (Sam's test style uses football analogies).
- When you merge a feature, **update the README's 🆕 Latest section**. Sam reads it to see what you changed.
