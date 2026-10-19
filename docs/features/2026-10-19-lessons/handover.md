# Handover: Lessons and tutor-created chats

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-20

## What was built
Feature (b) of [ADR 0005](../../decisions/0005-models-and-context-budget.md).

- **Lessons page** (`/lessons`, tutors):
  1. Pick one of your students, or yourself to try a lesson out, and see their chats (n of 5), each with Delete.
  2. **New lesson chat:** a title, topics (one per line) and notes for Prof AI.
  3. Lesson material:
     - upload a PDF (≤10 MB, ≤60 pages);
     - tick pages, with a preview and token count each; pages without text are flagged as possibly scanned;
     - "Add selected pages" puts their text into an editable box.
  4. A live meter against the 12k lesson cap, a "leave out answer pages" warning, and a licence checkbox whenever there's material.
- **Students:**
  - no "New chat";
  - their most recent chat opens automatically;
  - a banner shows the lesson title and topics;
  - with no chats yet, they see "Your tutor hasn't set up a chat for you yet".
- **Tutors' own Chat page** still has "+ New test chat" (no lesson), which "Save and try it" uses.
- **The lesson in the prompt:** `render_lesson(lesson)` is sent as the lesson layer on every turn. It's measured against `LAYER_CAPS[Layer.LESSON]` when saved (`validate_lesson`), so `assemble` never sees an oversized lesson.
- **Size limits on request bodies:** a new middleware (`prof_ai.request_limits`) refuses `/api` POST, PUT and PATCH requests over 1 MB (14 MB for the PDF upload) from `Content-Length`, before anything reads the body. A request with no length gets 411.

**Differences from the plan:**
- The lesson data shape (`Lesson`, `LessonSource`) lives in `chat/models.py`, to avoid a circular import. The rules (`render_lesson`, `validate_lesson`, limits) are in `prof_ai/lessons/rules.py`, not `lessons/models.py`.
- The upload size check is middleware rather than a FastAPI dependency, because dependencies run after the body has been read. It now protects every JSON route.
- A smoke test over real HTTP (uvicorn, in-memory stores, fake model) passed. **The UI hasn't been clicked through in a browser yet.**

## How to run / use it
- Nothing to deploy beyond the merge: no new Azure resources or settings.
- Tutors: **Lessons** in the top bar. Students: their chats appear on the Chat page.
- **Existing chats** that students started themselves stay. They have no lesson, still count towards the 5, and tutors can delete them on the Lessons page.

## Contracts other code can rely on
- **`Conversation`:** `lesson: Lesson | None` (`{title, topics[], notes, material, sources[{filename, pages[]}]}`) and `created_by: str | None`. The conversation is still partitioned by the student (`user_id`).
- **`ChatService`:**
  - `create_chat(actor, student, lesson=None, licence_confirmed=False)` raises `ChatRefusedError` 400 for an invalid lesson and 409 at `MAX_CHATS_PER_STUDENT = 5`. Callers check the actor may manage the student.
  - `delete_chat(student_id, conversation_id)`.
  - `start_conversation` is gone.
- **`ChatStore.delete_conversation(user_id, conversation_id)`.**
- **`prof_ai.lessons.rules`:** `render_lesson`, `lesson_tokens` and `validate_lesson`. The web meter mirrors `render_lesson` and the tidying (`web/src/lessons.ts`); a vitest test pins the same output as Python.
- **API:**

  | Method and path | Who | Result |
  |---|---|---|
  | `GET /api/students/{id}/chats` | tutors | `{chats[{id, title, topics, has_material, message_count, created_at, updated_at}], max_chats, max_lesson_tokens}` |
  | `POST /api/students/{id}/chats` `{lesson, licence_confirmed}` | tutors | 201 chat; 400 invalid or over cap; 409 at 5 |
  | `DELETE /api/students/{id}/chats/{chat_id}` | tutors | 204 |
  | `POST /api/lessons/extract` `{filename, pdf_base64}` | tutors | `{pages[{number, text, tokens}], max_lesson_tokens}`; 400 bad file; 413 too large |
  | `POST /api/chat/conversations` | **tutors only now** | a test chat for themselves; students get 403 |
  | `GET /api/chat/conversations/{id}` | owner | adds `lesson: {title, topics} \| null`. **Never the material or notes.** |

  - **Who can act on a student:** their tutor, any admin, or the tutor themselves. Anyone else gets 404.
  - **Audit:** `chat_created` and `chat_deleted` (`user_id` is the student, `reason` is the title).
- **Request bodies:** `/api` bodies are limited to 1 MB by default. If you add an upload route, give it an override in `main.py`.

## Tests added
- **`tests/lessons/`** (31 tests):
  - lesson validation: at the cap passes, over the cap fails, field limits, licence
  - a tutor creates a chat and the student uses it, with the lesson in the system prompt and the ledger
  - students see the title and topics but never the material or notes; the title is kept after the first message
  - students can't create chats; tutors can start test chats
  - cross-tutor 404s; unknown students 404; tutors can make chats for themselves; admins for anyone
  - the 5-chat limit, deleting to free a slot, and audit events; deleting a missing chat gives 404
  - an oversized or unlicensed lesson saves nothing; erasure removes lesson chats; sign-in required
  - extraction gives text and tokens per page; students refused; bad, unreadable and too-long PDFs give 400
  - an oversized upload gives 413 before it's read, and other routes are limited to 1 MB
- **`web/src/lessons.test.ts`** (9 tests): the meter matches the server's rendering and estimate; tidying; page joining; base64; the request shapes for the new API calls, and the 409 message.
- **Sam's earlier tests, changed:**
  - `tests/tutor_chat/conftest.py`: `Harness.start` creates chats through `ChatService.create_chat` as the user's tutor, because students can't start them over the API.
  - `tests/context_budget/`: the detail response now includes `lesson`, and the global-cap test uses one chat (the 5-chat limit).

## Known issues / TODOs
- **Not clicked through in a browser.** Please try it after the merge:
  1. Set up a lesson for yourself on **Lessons** using a real chapter PDF.
  2. Chat in it.
  3. Check `prof chats show` for the `lesson` size in the context line.
- **Answer pages** are on the tutor to leave out. Extraction shows them like any other page (the smoke test's "Answers: 1. 2:3" came straight through). The prompt holds up when they're present (dilution eval), but they shouldn't be there (R4).
- **Scanned PDFs** have no text layer, so pages come back empty. OCR (Document Intelligence) is a later option.
- **No lesson editing:** to change a lesson, delete the chat and set up a new one. That also deletes the student's messages.
- **pypdf's extraction mangles maths layout** (fractions, superscripts). Tutors can fix the text in the box.
- **Throughput:** a turn with a full 12k lesson is ~15k tokens of the 50k a minute. The quota task matters more now.
- **Library chapters:** building a lesson from a book in the content store is a natural follow-up.

## For the other dev
- **Students can't start chats any more.** Use **Lessons** to set chats up. Tests that need a chat should call `Harness.start`, which goes through the service.
- **Anything that adds to a lesson** must go through `validate_lesson`, so the cap is enforced when it's saved.
- **Never return `lesson.material` or `lesson.notes` to a student.** The API tests check this.
