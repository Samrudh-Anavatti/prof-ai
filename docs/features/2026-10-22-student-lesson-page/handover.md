# Handover: The student's lesson page

- **Owner:** punji
- **PR:** see the PR for `feat/student-lesson-page`
- **Merged:** pending

## What was built
As planned, plus layout fixes found in a browser check:
- **Lesson panel** (`web/src/LessonPanel.tsx`) above any lesson chat that has questions or worked examples:
  - Worked examples: open at *Step by step*, folded at *Balanced* and *Stretch*. They scroll on their own (30% of the screen height, 22% on phones).
  - "N of M done" and question chips: amber while working, ✓ when correct.
  - The current question, rendered with maths and line breaks kept.
  - For students: three help buttons that ask Prof AI straight away, and *Check my answer*.
  - For tutors: the same view, with tries and help messages per question, and no help buttons or answer box.
  - The panel takes at most 60% of the chat column (45% on phones), so the conversation stays visible.
- **The current question** is the one the student picked, otherwise the first one not yet correct. Messages sent while it's open are tagged with it and show a "Question A1.2" label.
- **Tagged turns:** `ChatMessage.question`. A tagged message brings that question, and its answer labelled "never reveal it", into that one turn's reference material (`question_reference`), so nothing is stored in history. Unknown question numbers are ignored.
- **Check my answer:** `POST /api/chat/conversations/{id}/check` with `{question, answer}`, for the signed-in owner of the chat only.
  - **No key:** 409 with a friendly message.
  - **Exact match** after ignoring case, spaces, `$`, `\,` and a trailing full stop: "That's right. Well done!", with no model call, even with the kill switch on.
  - **Otherwise a model check** (`chat/prompts/check_answer.md`) on the chat's own (approved) model: budgets, kill switch, rate limit, 300 output tokens, charged to the student.
  - **Leak guard:** feedback on a wrong answer that contains the key is replaced with a neutral "not yet". The guard ignores spacing around maths symbols and allows a full stop at the end of a sentence.
  - **Recording:** each check saves an `Attempt` and adds the exchange to the chat (`checks_answer=True`), so the tutor and later turns can see it.
- **Progress:** `ConversationDetail.progress`, one entry per question: `{number, status, attempts, help_messages}`. It's shown to the student and the tutor.
- **Student view:** `LessonOverview` now includes `support`, `worked_examples` and `questions` (number and text only).
- **Markdown:** `Markdown` gained `lineBreaks` for tutor content (worksheets put each equation on its own line).

## How to run / use it
- Set up a lesson with extracted questions (Lessons page), then open it as the student.
- As a tutor, open the student's chat from the Lessons page to see their progress.

## Contracts other code can rely on
- `ChatMessage.question`, `ChatMessage.checks_answer`, `Attempt`, `Conversation.attempts` (`chat/models.py`).
- `chat/checking.py`: `question_progress`, `question_reference`, `matches_key`, `leaks_key`, `check_request`, `parse_check`, `QuestionProgress`.
- `ChatService.begin_turn(..., question=None)` and `ChatService.check_answer(owner, chat_id, question, answer) -> CheckResult`.
- API:
  - `NewMessage.question`
  - `MessageOut.question`
  - `LessonOverview.support | worked_examples | questions`
  - `ConversationDetail.progress`
  - `POST .../check` returns `{correct, feedback, progress}`
- Web:
  - `ChatEndpoints.send(content, handlers, toTutor?, question?)` and `ChatEndpoints.check?`
  - `sendMessage(…, toTutor, question)` and `sendStudentChatMessage(…, options, question)`
  - `checkAnswer(…)`
  - `progress.ts` helpers
  - `Markdown`'s `lineBreaks`

## Tests added
- `tests/student_lesson_page/`:
  - The student's view shows questions without answers.
  - A question and its answer join only the tagged turn, never the history.
  - Unknown tags are ignored.
  - An exact match is correct with no model call.
  - A model check is recorded and charged.
  - Leaking feedback is replaced.
  - No key means no check; bad checks are refused.
  - Only the owner can check.
  - The kill switch stops model checks only.
  - Progress counts are right, and the tutor's view matches.
  - Unit tests for matching and the leak guard.
- `web/src/studentLessonPage.test.ts`:
  - The next-question and label helpers.
  - The panel: worked example open at *Step by step*, folded at *Stretch*, and no answer box or help for tutors.
  - The request shapes.
- **Changed to the new contract (Sam's tests):** these pin the exact response shapes, and this feature adds fields to them on purpose. They're extended by exactly those fields and stay just as strict.
  - `tests/context_budget/test_memory_and_budgets.py::test_the_ledger_and_summary_are_not_sent_to_the_browser`: adds `progress` and the message field `question`.
  - `tests/lessons/test_lesson_chats.py::test_students_see_the_lesson_title_and_topics_but_never_material_or_notes`: adds `support`, `worked_examples` and `questions`, all empty for that lesson.

## Known issues / TODOs
- **Not exercised end to end in a browser:** that would need real lessons in the shared database. The panel was checked as a static render with the real stylesheet at desktop and phone widths. Please try it on the live app.
- The check prompt and the tagged-turn reference haven't been through `prof eval dilution`. Worth adding cases: a student begs for the answer while a question is open, and leaking check feedback.
- Tutors still can't edit a saved lesson's questions.
- Flags for rapid guessing or begging for answers are counted but not flagged (L11, planned).
- An exact match on a short key like "4" accepts "4" even if the student's working is wrong. That's acceptable for a self-check; the tutor sees every attempt.

## For the other dev
- ADR 0006 (proposed) now has its second stage built.
- Two of your tests were extended for the new fields (above). Please check you're happy with them.
- Never put `Question.answer` in a stored message or the lesson layer (CLAUDE.md).
