# Plan: Teaching style editor in the web UI

- **Owner:** sam
- **Branch:** `sam/teaching-style-editor`
- **Date:** 2026-10-18

## Goal
A signed-in tutor can read and edit their own `teaching-style.md` in the web app, see exactly what Luna is told, and try the change straight away in a new chat. Today this needs the CLI and Azure access. Punjy should be able to tune the style and watch replies change without touching a terminal.

Also in this branch: a much fuller front-page `README.md` (architecture diagram, decisions, latest feature, links, open items), with a CLAUDE.md rule to keep its "Latest" section current on every merge.

## Approach
- **API** (tutors only, via `require_role(Role.TUTOR)`; the tutor ID always comes from sign-in):
  - `GET /api/teaching-style` → `{content, system_prompt, max_bytes}`. `content` is `""` when no file exists. `system_prompt` is the fully assembled prompt the tutor's own chats get (base + style + their profile).
  - `PUT /api/teaching-style` `{content}` → the same shape after saving. Validation is `ProfileStore.put`'s: not empty, at most 8 KB. Errors are 400 with `{detail}`.
  - Each save writes an `AuditEvent` (`action="teaching_style_updated"`, actor = the tutor's email).
- **Profile store wiring:** `create_app` gains a `profile_store` argument and builds one `ProfileStore` that the chat service and the new router share. No store configured → 503.
- **Infra:** the web app's role on the `profiles` container goes from Storage Blob Data **Reader** to **Contributor**, still scoped to that one container. The old reader assignment is removed by hand after the deploy (Bicep doesn't delete).
- **UI:**
  - A "Teaching style" link in the top bar for tutors only. It routes client-side to `/teaching-style` (the server already serves the shell for any page path).
  - A Markdown textarea with a live byte counter against 8 KB, **Save**, and **Save and try it**, which saves then opens a new chat.
  - "What Luna is told": the assembled system prompt, shown as plain text in a collapsible panel.
  - A note that edits apply from the next message, to the tutor and all their students.
- No change to how chat reads profiles: it reads the blob on every turn, so a save takes effect on the next message.

## Risks
| Risk | Control |
|------|---------|
| **A student edits a tutor's style or reads the base prompt** (R1, R8) | `require_role(Role.TUTOR)` on both endpoints; tests for a student getting 403 on both. The path is always `profiles/<signed-in tutor id>/…`, never taken from the request. |
| **A tutor edits another tutor's style** | No user ID in the request at all; tested by Punjy's save not changing Sam's file or Sam's students' prompt. |
| **The app's managed identity can now write profiles** | Contributor is scoped to the `profiles` container only (not `content`, `sources` or `answer-keys`). Blob soft delete (14 days) allows recovery. Only the teaching-style path is reachable through the API; `profile.md` stays CLI-only. |
| **Cross-site request forgery** | The Easy Auth cookie is sent cross-site only on top-level navigations; the PUT needs a JSON body, and a `text/plain` body is rejected (tested). No CORS is configured, so another origin can't send a JSON PUT. |
| **XSS through the style text** (R18) | Rendered as plain text in a textarea and a `<pre>`; no HTML rendering. CSP unchanged. |
| **Cost** (R3) | No model calls in this feature. "Save and try it" uses the normal chat path with its budgets. |
| **A bad style degrades tutoring** (R4, R6) | The base prompt stays first and the style is appended after it; tutors are trusted. Every save is audited, and the prompt preview shows the effect. |
| **Child safety** | Students never see or reach this page. The base prompt's safeguarding rules come before the tutor's text. |
| **Failure** | Blob errors on read or save → 503 and nothing changes; the UI keeps the unsaved text. |

## Files / modules touched
- `src/prof_ai/profiles/api.py` (new): the teaching-style router.
- `src/prof_ai/main.py`: `profile_store` wiring and router include.
- `infra/main.bicep`: app role on `profiles` → Contributor.
- `web/src/api.ts`, `web/src/App.tsx`, `web/src/TeachingStylePage.tsx` (new), `web/src/ChatPage.tsx` (start a fresh chat on arrival), `web/src/styles.css`.
- `tests/teaching_style_editor/`, `web/src/api.test.ts`.
- `README.md`, `CLAUDE.md`, `docs/product/risks.md`, `docs/features/INDEX.md`.

## Contracts added or changed
- `GET /api/teaching-style` and `PUT /api/teaching-style` as above.
- `create_app(..., profile_store=None)`.
- Audit action `teaching_style_updated`.
- README "Latest" section: updated by whoever merges a feature (rule in CLAUDE.md).

## Tests to add
`tests/teaching_style_editor/`:
- a tutor reads an empty style, saves one and reads it back, with the assembled prompt
- the save lands at `profiles/<tutor-id>/teaching-style.md` and changes the next chat prompt for that tutor's students only
- students get 403 on GET and PUT
- empty and oversized styles get 400
- a non-JSON body is rejected
- each save is audited
- no profile store → 503

`web/src/api.test.ts`: the client sends a PUT with a JSON body and surfaces a 400 detail.

## Open questions
- Should tutors also edit each student's `profile.md` in the UI? Not now; it holds data about children, so it needs its own data review (R10).
