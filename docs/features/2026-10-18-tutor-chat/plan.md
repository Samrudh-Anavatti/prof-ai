# Plan: Tutor chat PoC with per-user AI profiles

- **Owner:** sam
- **Branch:** `sam/tutor-chat`
- **Date:** 2026-10-18

## Goal
The first usable proof of concept: a signed-in user chats with Luna (`gpt-5.6-luna`), which is system-prompted to act as a tutor, in a lightly branded web UI. What the AI is told depends on who is signed in, through per-user profile files that tutors write. Knowledge-base injection and memory come later and plug into the same prompt assembly.

## Approach
- **Prompt assembly** (`prof_ai.chat.prompts`). The system prompt is built from layers, in this order:
  1. **Base tutor prompt**, in the repo (`src/prof_ai/chat/prompts/tutor.md`). It covers the tutoring style (guide, don't hand over answers), age-appropriate tone, scope, and what to do with distress ("talk to your tutor or a trusted adult").
  2. **Teaching style** of the user's tutor: `profiles/<tutor-id>/teaching-style.md`. For a student this is their tutor's file; for a tutor it's their own. This is how Sam's students and Punji's students get different behaviour.
  3. **The user's own profile**: `profiles/<user-id>/profile.md` (first name, year group, subjects, goals, tone notes).
  4. Later: knowledge-base context and memory slot in here.

  Each profile layer is capped at 8 KB. A missing file is skipped.
- **Profile store:** a new private Blob container, `profiles`. The web app gets *read* access to this container only. Tutors write through the CLI with their `az login`. Students can't edit profiles.
- **CLI:**
  - `prof profiles show <email>`: prints both files and the fully assembled system prompt, so you can see exactly what the AI gets.
  - `prof profiles set <email> --profile file.md` / `--teaching-style file.md` (teaching style is for tutors only).
  - `prof chats list <email>` / `prof chats show <conversation-id> --user <email>`: read transcripts.
- **Model client** (`prof_ai.chat.model`): the `openai` SDK against Foundry's v1 endpoint with an Entra token from managed identity (no keys), streaming. It sits behind a small protocol so tests use a fake.
- **API** (all under `/api/chat`, all `CurrentUser`; the user ID always comes from sign-in, never from the request):
  - `GET /api/chat/conversations`: your conversations (`id`, `title`, `updated_at`).
  - `POST /api/chat/conversations`: start one.
  - `GET /api/chat/conversations/{id}`: messages. 404 if it isn't yours (it's partitioned by user, so it isn't even looked up elsewhere).
  - `POST /api/chat/conversations/{id}/messages` `{content}`: streams the reply as server-sent events (`delta`, `done`, `error`).
- **Storage (Cosmos):**
  - `conversations` (pk `/user_id`): one document per conversation, holding messages, token usage and any flags.
  - `usage` (pk `/user_id`): one document per user per UTC day.
- **UI:**
  - A chat page: conversation list, message thread, streamed replies, a "New chat" button.
  - Plain-text rendering only (no Markdown or HTML from the model yet).
  - Basic Prof AI branding: wordmark, colour palette, favicon.

## Risks
| Risk | Control in this feature |
|------|------|
| **R3 cost** | 2,000-character input cap; 1,000 output-token cap with low reasoning effort; only the last 20 messages are sent; **per-user daily budget of 50k tokens** with a hard stop; **global daily cap of 500k tokens** across all users; `CHAT_ENABLED=false` app setting as a kill switch; one reply in flight per user; 10 messages a minute per user. The £50 Azure budget alert stays as the backstop. |
| **R1 jailbreak / prompt injection** | The base prompt sets scope; Foundry's DefaultV2 content filters (jailbreak detection included) stay on. Profiles are written only by tutors, so the user can't inject into the system prompt. A filter hit is stored on the conversation as a flag for the tutor. Prompt Shields and auto-lock come with the full guard pipeline later. |
| **R5 harmful output** | Foundry content filters on input and output. A filtered reply shows a neutral message and is flagged. |
| **R8 cross-user data** | Conversations and usage are partitioned by the signed-in user's ID, with no user ID in any request. Tests check that another user's conversation returns 404 and that profile layers come from the right user and tutor. |
| **R4 answer leakage** | Out of scope until assignments exist. The base prompt tells the model to coach, not solve. |
| **R6 wrong answers** | The base prompt says to admit uncertainty and suggest asking the tutor. Tutors can read transcripts with `prof chats show`. |
| **R10 / R16 children's data** | **PoC use is limited to Sam, Punji and synthetic test accounts** until R16 and parental consent are resolved. Profiles hold only first name and learning details. Transcripts stay in Cosmos (UK South), and no message content goes into logs. Retention policy is still to decide. |
| **R11 safeguarding** | The base prompt sends distress to a trusted adult and the tutor. The automatic tutor flag on self-harm categories comes with the guard pipeline, which **must ship before real students use chat.** |
| **R18 XSS** | Model output is rendered as React text, never HTML. |
| **Failure** | If Foundry, Cosmos or the profile store fails, the user gets "unavailable" and nothing is half-saved: the user's message is stored only alongside a completed reply. If the budget check fails, the request is refused (fails closed). |

## Files / modules touched
- **New:** `src/prof_ai/chat/` (`prompts.py`, `prompts/tutor.md`, `model.py`, `store.py`, `cosmos_store.py`, `limits.py`, `api.py`, `service.py`), `src/prof_ai/profiles/` (store over the existing `BlobBackend`), `web/src/chat/*`, `tests/tutor_chat/`
- **Changed:** `main.py`, `config.py`, `cli.py`, `infra/main.bicep` (Blob container `profiles` + app reader role; Cosmos containers `conversations` and `usage`; app settings), `requirements.txt` (`openai`), `.env.example`, `web/src/App.tsx`, `web/src/api.ts`, docs

## Contracts added or changed
- **Blob layout:** `profiles/<user-id>/profile.md` and `profiles/<user-id>/teaching-style.md`.
- **Prompt assembly order:** base → tutor's teaching style → user profile → (future) knowledge context.
- **Cosmos:**
  - `conversations` `{id, user_id, title, messages[{role, content, at}], usage{input_tokens, output_tokens}, flags[], created_at, updated_at}`.
  - `usage` `{id: "<user_id>:<YYYY-MM-DD>", user_id, date, tokens}`.
- **The chat API above**, including the SSE event names `delta`, `done` and `error`.
- **App settings:** `CHAT_ENABLED`, `CHAT_DAILY_USER_TOKENS` (50000), `CHAT_DAILY_GLOBAL_TOKENS` (500000), plus the existing `FOUNDRY_ENDPOINT`, `CHAT_DEPLOYMENT` and `STORAGE_ACCOUNT_URL`.

## Tests to add
`tests/tutor_chat/`, all offline with a fake model, an in-memory store and a fixed clock:
- prompt layering for a student, a tutor, and a missing profile; size cap
- Sam's student and Punji's student get different system prompts
- conversations are isolated per user (404 for someone else's)
- every chat endpoint needs sign-in
- input cap, daily user budget, global cap, kill switch and rate limit all refuse before any model call
- usage is recorded from the model's reported tokens
- history is truncated to 20 messages
- a content-filter hit returns a neutral message and is flagged
- the SSE stream has the right event shape
- a model failure saves nothing
- CLI `profiles` and `chats`

Plus vitest for the SSE client parsing.

## Open questions
- **Infra:** Sam runs `bash scripts/deploy-infra.sh` after review. It adds one Blob container and two Cosmos containers; on serverless they're £0 until used.
- **Budget numbers:** 50k tokens per user per day and 500k globally are starting points; tune them after seeing real usage.
- **Retention:** how long to keep transcripts (decide before real students).
