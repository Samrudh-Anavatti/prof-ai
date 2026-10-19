# Plan: Shared tutor–student chat with @AI

- **Owner:** sam
- **Branch:** `sam/shared-chat`
- **Date:** 2026-10-20

## Goal
Feature (c) of [ADR 0005](../../decisions/0005-models-and-context-budget.md): the student and their tutor write in the same lesson chat, and **Prof AI only replies to a message that mentions `@AI`**, from either of them. Messages without `@AI` cost nothing. Tutors are exempt from the per-user budget; their spend still counts towards the global cap.

## Approach
- **Authors on messages:**
  - A human message is saved with `author` (`student` or `tutor`) and `author_name`, taken from the signed-in user, never from the request.
  - Messages saved before this feature have no author, and are treated as from the chat's owner.
- **Labels the model can trust (R25):**
  - `assemble` prefixes every human message it sends to the model with a label such as `⟦Student Alex⟧` or `⟦Tutor Sam⟧`.
  - Any `⟦` or `⟧` in the message text is removed first, so a student can't forge a tutor label.
  - `tutor.md` explains the labels; says tutors may guide the teaching (for example, ask for a worked example); and says the safety rules apply whoever is writing.
- **When the AI replies:**
  - In a student's chat, only when the message matches `@AI` (case-insensitive, a whole word).
  - In a tutor's own test chat, always (there's no-one else to talk to).
  - A message without `@AI` is saved straight away, with no model call and no budget check. It's still rate-limited (10 a minute per user).
- **The AI sees the shared conversation:** the history window holds everyone's messages, so it can use what the tutor and student said to each other.
- **Who pays and whose context:**
  - The person who mentioned `@AI` pays; tutors skip the per-user budget.
  - The prompt's profile and teaching style always come from the **chat's owner (the student)** and their tutor, whoever is writing.
- **Simultaneous writes:**
  - Two people can now write to the same conversation document at once (a tutor posts while the AI reply is saving). That would lose a message under the current last-write-wins `upsert`.
  - `ChatStore.update_conversation(user_id, id, change)` reads, applies `change`, and writes with an ETag check (`If-Match`), retrying up to 5 times on a 412.
  - Every save after a chat is created goes through it: turns, flags, summaries.
  - Messages stay in the one document; the 200-message cap keeps it well under 2 MB.
- **Live updates by polling:**
  - `GET …/version` returns `{updated_at}`, using a one-field query (~3 RU, whatever the document's size).
  - The open chat polls it every 5 s while the tab is visible, and fetches the full detail only when it changes.
- **API:**
  - **Student**, unchanged paths:
    - `POST /api/chat/conversations/{id}/messages` (still server-sent events).
    - `done` now carries `{title, ai}`, where `ai` says whether Prof AI replied.
    - `GET /api/chat/conversations/{id}/version`.
  - **Tutor**, on their students' chats:
    - `GET /api/students/{sid}/chats/{cid}` (the detail),
    - `POST /api/students/{sid}/chats/{cid}/messages`,
    - `GET /api/students/{sid}/chats/{cid}/version`.
  - The detail's messages gain `author` (`student`, `tutor` or `ai`) and `author_name`.
- **Web:**
  - Bubbles: your own messages on the right; others on the left, labelled with the author's name (or "Prof AI").
  - The composer has **Send** (to the chat) and **Ask Prof AI** (adds `@AI` if it's missing).
  - Tutors open a student's chat from the Lessons page (`/lessons/{studentId}/{chatId}`).
  - Both sides poll.

## Risks
| Risk | Control |
|------|------|
| **R24 one-to-one adult–child messaging** | Every message is stored on the platform with its author and time, can be read with `prof chats show`, and is erased with the student. Messages without `@AI` don't go through Foundry's filter. **The guard pipeline must screen every student message before real students** (already required). Retention and parent visibility are still open (R10). |
| **R25 a student impersonates the tutor** | Labels are added by the server from the signed-in role; `⟦⟧` are removed from message text; the prompt trusts only those labels. A new eval scenario checks a forged tutor label is ignored. |
| **R8 cross-student access** | Tutor routes reuse `managed_student`: another tutor's student gets 404. Students only reach their own partition. |
| **R3 cost** | Plain messages never call the model. `@AI` turns keep every existing check (input cap, kill switch, budgets, rate limit, one reply in flight). |
| **Lost messages from simultaneous writes** | ETag-checked updates with retries. A test writes from two sides "at once". |
| **Polling cost** | One-field query (~3 RU), every 5 s, only for open, visible chats. Ten open tabs for an hour is ~22k RU: pennies on serverless. |
| **Prompt change** | `tutor.md` changes, so `prof eval dilution` is re-run (it must stay all-pass). Two new scenarios: a forged tutor label, and a real tutor asking for a worked example. |

## Files / modules touched
- **Changed:**
  - backend: `chat/models.py`, `chat/context.py` (labels), `chat/service.py`, `chat/store.py`, `chat/cosmos_store.py`, `chat/api.py`, `chat/memory.py` (speaker names), `chat/prompts/tutor.md`, `lessons/api.py`
  - evals: `evals/scenarios.json`, `evals/dilution.py` (authors)
  - web: `web/src/api.ts`, `web/src/ChatPage.tsx`, `web/src/LessonsPage.tsx`, `web/src/App.tsx`, `web/src/styles.css`
  - `tests/tutor_chat/conftest.py` (the store fake gets `update_conversation` and `conversation_version`)
  - docs
- **New:**
  - `web/src/ChatThread.tsx` (the thread, composer and polling, shared by students and tutors), `web/src/TutorChatPage.tsx`
  - `tests/shared_chat/`

## Contracts added or changed
- `ChatMessage.author: "student" | "tutor" | None` and `ChatMessage.author_name: str | None`.
- `ChatService.begin_turn(sender, owner, conversation_id, content)`; `Turn` carries `ask_ai`.
- `ChatStore.update_conversation(user_id, id, change) -> Conversation` and `ChatStore.conversation_version(user_id, id) -> datetime | None`.
- SSE `done` is `{title, ai}`.
- `ContextInput` takes `owner_name` for labelling older messages. `assemble` labels the human messages.
- The tutor routes above, and `GET …/version` on both sides.

## Tests to add
`tests/shared_chat/`:
- **Plain messages:** a student or tutor message without `@AI` is saved with its author and makes no model call; with `@AI` the model replies and `done` has `ai: true`; a tutor's test chat always replies.
- **The model's view:** labels; `⟦Tutor⟧` typed by a student is stripped; the tutor's earlier messages appear in the history.
- **Context and billing:** a tutor's `@AI` in a student's chat uses the student's profile and the tutor's style, and is charged to the tutor (exempt from the student budget).
- **Access:** another tutor gets 404; the student can't use the tutor routes (403).
- **Live updates:** the version changes after any message.
- **Simultaneous writes:** a tutor message saved while an AI turn is streaming survives, as does the AI turn.
- **Summaries** name speakers by author.
- **Rate limit:** plain messages still count towards it.

Plus vitest for the `{title, ai}` result and the tutor message path.

## Open questions
- **Telling the tutor about new messages** (beyond polling while open) is a later feature: email or an unread badge.
- **Real students** still wait on the guard pipeline (R11, R24).
