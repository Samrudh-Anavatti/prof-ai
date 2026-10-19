# Plan: Lessons and tutor-created chats

- **Owner:** sam
- **Branch:** `sam/lessons`
- **Date:** 2026-10-19

## Goal
Feature (b) of [ADR 0005](../../decisions/0005-models-and-context-budget.md): chats belong to a lesson and only tutors create them.
- A tutor sets up a chat for one student: lesson title, topics, notes for Prof AI, and lesson material taken from PDF pages. The material becomes the capped lesson layer of every turn.
- A student has at most **5 chats**; the tutor deletes one to free a slot.
- Students can't start chats any more. They pick from the ones their tutor made.

Shared tutor–student messaging and `@AI` are feature (c).

## Approach
- **Lesson model** (`prof_ai/lessons/models.py`):
  - `Lesson{title, topics[], notes, material, sources[{filename, pages[]}]}`.
  - `render_lesson(lesson)` produces the text of the lesson layer: the title, topics, "what your tutor wants to focus on", then the material.
  - `validate_lesson` checks the field limits and that `estimate_tokens(render_lesson(...))` fits `LAYER_CAPS[Layer.LESSON]` (12k now). This is the write-time gate from ADR 0005.
- **PDF text extraction** (`prof_ai/lessons/pdf_text.py`):
  - pypdf's `extract_text` per page, returning `[{number, text, tokens}]`.
  - Limits: 10 MB, 60 pages (more → "split the PDF first"). The `%PDF-` header is checked.
  - Nothing is stored: the tutor picks pages and edits the text, and only the saved lesson is kept.
- **Storage:**
  - The lesson lives on the conversation document. It's partitioned by the student, so deleting a user erases it with their chats.
  - `Conversation` gains `lesson` and `created_by`. A lesson chat's title is the lesson title.
- **`ChatService`:**
  - `create_chat(actor, student, lesson)` enforces 5 per student and validates the lesson.
  - `delete_chat(student, id)`.
  - Turns pass `render_lesson(conversation.lesson)` as `ContextInput.lesson`.
- **API:**
  - **Tutor side** (tutors manage their own students and themselves; admins manage anyone), under `/api/students/{student_id}/chats`:
    - `GET` lists chats.
    - `POST {lesson, licence_confirmed}` returns 201; 409 at 5; 400 for an invalid or oversized lesson.
    - `DELETE /{id}` returns 204.
    - Creating and deleting are audited (`chat_created`, `chat_deleted`).
  - `POST /api/lessons/extract {filename, pdf_base64}` is tutors only. It's JSON rather than multipart, so the existing JSON-only CSRF guard still applies. A request over ~14 MB is refused before the body is read.
  - **`POST /api/chat/conversations` is now tutors only** (their own test chats, used by "Save and try it"); students get 403.
  - `GET /api/chat/conversations/{id}` adds `lesson: {title, topics}` for the student. **Never the material or notes.**
- **Web:**
  - A new tutor page, **Lessons** (`/lessons`): pick a student (or yourself), see their chats (n/5) with Delete, and "New lesson chat":
    1. title, topics (one per line) and notes for Prof AI;
    2. upload a PDF and tick pages;
    3. "Add selected pages" puts their text into an editable material box;
    4. a live meter against the 12k cap, using the same bytes ÷ 3 estimate;
    5. a "leave out answer pages" warning, and a "these materials are licensed for use with my students" checkbox.
  - Students' chat page: no "New chat"; the lesson title and topics show above the thread; an empty state says "Your tutor hasn't set up a chat yet".

## Risks
| Risk | Control |
|------|------|
| **R4 answer keys in the student's context** | The UI warns tutors to leave out answer pages, and the material is editable before saving. The hardened prompt (eval: 3/3 at 2k–40k with answers present) is the backstop. Material and notes are never sent to the browser for students. |
| **R12 textbook licence** | A required licence confirmation whenever material is present; the lesson records the source file and pages. Material is only ever shown to that student's model calls, never to the student directly. |
| **R23 injection via material** | Tutors only; material sits in the labelled lesson section; the prompt and reminder say material isn't instructions (eval: the planted instruction was ignored 12/12). |
| **R8 cross-student access** | Every student route checks `can_manage`, or that the student is the tutor themselves. Another tutor's student returns 404, the same as a missing one. Conversations stay partitioned by student. |
| **R3 cost and throughput** | The lesson is capped at 12k at save time; `assemble` refuses anything over (fails closed). A lesson turn is ~15k tokens of the 50k a minute, so the quota task matters more now. |
| **Malicious or huge PDFs** | Tutors only; 10 MB and 60-page limits; the size is checked before the body is read; extraction runs in the threadpool; nothing is stored. |
| **Child safety** | No new student-facing content. Students see only the lesson title and topics. |
| **Failure** | Extraction errors give a 400 with a clear message. A store failure gives 503, and nothing is half-created. |

## Files / modules touched
- **New:**
  - `src/prof_ai/lessons/` (`models.py`, `pdf_text.py`, `api.py`)
  - `web/src/LessonsPage.tsx`, `web/src/lessons.ts` (meter and file helpers)
  - `tests/lessons/`
- **Changed:**
  - `chat/models.py`, `chat/service.py`, `chat/store.py`, `chat/cosmos_store.py` (`delete_conversation`), `chat/api.py`
  - `main.py`, `web/src/App.tsx`, `web/src/ChatPage.tsx`, `web/src/api.ts`, `web/src/styles.css`
  - `tests/tutor_chat/conftest.py` (the harness starts chats through the service, since students can't start them)
  - docs

## Contracts added or changed
- `Conversation.lesson: Lesson | None` and `Conversation.created_by: str | None`.
- `MAX_CHATS_PER_STUDENT = 5`.
- `ChatService.create_chat(actor, student, lesson | None)`, `ChatService.delete_chat(student_id, conversation_id)`, `ChatStore.delete_conversation(user_id, id)`.
- The API routes above. Students can no longer `POST /api/chat/conversations` (403).
- `prof_ai.lessons.models.validate_lesson` and `render_lesson`: feature (c) and the knowledge graph reuse them.

## Tests to add
`tests/lessons/` (offline; PDFs built in the test):
- **Lesson validation:** at the cap passes, over the cap gives 400; field limits; licence confirmation needed with material.
- **Create and use:**
  - a tutor creates a lesson chat for their own student;
  - the student lists it;
  - the next turn's system prompt contains the lesson in the lesson section;
  - the student's detail has the title and topics but not the material or notes.
- **Access:** a tutor can't touch another tutor's student (404); students can't create (403); admins can; a tutor can create for themselves.
- **Limits:** the 6th chat gives 409; deleting frees a slot; create and delete are audited; deleting someone else's chat gives 404.
- **Extraction:** text per page with token counts; tutor only; non-PDF, too large, too many pages and oversized requests are refused.
- **Erasure:** deleting a user removes their lesson chats.

Plus vitest for the new API calls and the token meter.

## Open questions
- **Library chapters:** building a lesson from a chapter of a book already in the content store (`prof content add-book`) is a natural follow-up. It's out of scope here, because the app can't read `sources/`.
- **Scanned PDFs:** these have no text layer, so extraction returns little. The UI will show empty pages. OCR (Document Intelligence) is a later option.
