# Plan: The student's lesson page

- **Owner:** punji
- **Branch:** `feat/student-lesson-page`
- **Date:** 2026-10-22

## Goal
A lesson with questions becomes a page a student can work through, not a blank chat box ([ADR 0006](../../decisions/0006-worksheet-first-lessons.md), proposed):
- The worked examples, open first at *Step by step* and folded away at *Balanced* and *Stretch*.
- The questions, one at a time, each with its status.
- Help buttons for the current question, and the chat underneath.
- **Check my answer**, which says right or "not yet" with a pointer, never the answer.

The tutor sees each question's progress in the same chat.

## Approach
- **Messages carry a question:** `ChatMessage.question` (a question number) and `NewMessage.question`. A message about a question attaches that question to the turn as reference material: its text, plus the tutor's answer labelled "only to check the student's working; never reveal it". It goes in the existing per-turn reference layer (ADR 0005), so it's never stored in history and no new layer is needed.
- **Check my answer:** `POST /api/chat/conversations/{id}/check` with `{question, answer}` (the student, in their own chat).
  - **No answer key:** "Your tutor hasn't added an answer for this one", with no model call and no attempt recorded.
  - **Plain comparison first:** spaces, `$`, case and simple formatting are normalised. If it matches, the answer is correct, with no model call, so it's free and instant.
  - **Otherwise one model call** (`chat/prompts/check_answer.md`) returns `{"correct", "feedback"}`. It runs through `ChatService`: kill switch, budgets, rate limit, the chat's model (approved only, since this is a student's chat), and the cost charged to the student.
  - **Leak guard:** if the feedback on a wrong answer contains the key, it's replaced with a neutral "not yet" (R4).
  - **Recording:** the attempt is saved as `Attempt(question, answer, correct, at)`, and the exchange is added to the chat as a student message plus a Prof AI reply, so the tutor sees it and later turns have the context.
- **Progress:** `ConversationDetail.progress`, one entry per question: `{number, status: not_started | working | correct, attempts, help_messages}`. It's computed from attempts and tagged messages, and shown to the student and the tutor.
- **What the student sees:** `LessonOverview` gains `support`, `worked_examples` and `questions`, as number and text only. **Never answers.**
- **Web:** a lesson panel above the chat with a worked examples section, question chips (✓ for correct), the current question in full with help buttons ("What is this asking?", "Give me a hint", "Check my working") and an answer box with *Check my answer*. Messages sent while a question is open are tagged with it and show a small label. Tutors see the same panel with attempt counts.

## Learning check
- **L1 Worked examples** and **L2 expertise reversal:** the worked example leads at *Step by step* and folds away for confident students.
- **L3 Retrieval practice:** the student answers each question, not Prof AI.
- **L4 Useful feedback:** the check says what to look at again, not just right or wrong.
- **L7 Step-based hints:** help is about the current question.
- **L11 Gaming the system:** attempts are counted per question and shown to the tutor.

## Risks
- **R4 (answers handed over):** answers go only into the one tagged turn and the check call. They're never stored in history, the lesson layer or anything sent to a student. The leak guard covers the check's feedback, and the base prompt plus the reference label cover chat turns. Tested: no answer in any student response, and the guard replaces leaking feedback.
- **R7 (wrong checking):** the plain comparison only ever says "correct" on an exact match. Model checks are provisional, the tutor sees every attempt, and a missing key means no check.
- **R3 (cost):** the plain comparison costs nothing. Model checks are capped at 300 output tokens and budgeted like chat turns. Rapid guessing is bounded by the rate limit.
- **R8 (other students' data):** the check route is the student's own chat only; the tutor checks nothing on their behalf. Tested.
- **R11:** student text in a check goes to the model like any message, so content filter hits are flagged as before.

## Files / modules touched
- `src/prof_ai/chat/`: `models.py`, `service.py`, `api.py`, new `checking.py`, new `prompts/check_answer.md`
- `web/src/`: `api.ts`, `ChatThread.tsx`, new `LessonPanel.tsx`, new `progress.ts`, `ChatPage.tsx`, `TutorChatPage.tsx`, `styles.css`
- Docs: ADR 0006, CLAUDE.md, README, INDEX, risks, learning science

## Contracts added or changed
- `ChatMessage.question`, `NewMessage.question`, `Conversation.attempts: [Attempt]`
- `LessonOverview.support | worked_examples | questions` (no answers); `ConversationDetail.progress`; `MessageOut.question`
- `POST /api/chat/conversations/{id}/check` → `{correct, feedback, progress}`
- `ChatService.check_answer(student, conversation_id, question, answer)`

## Tests to add
`tests/student_lesson_page/`:
- a tagged message carries the question and its answer only in that turn, and nothing in the history
- the student's view has the questions without answers
- an exact match is correct with no model call
- a model check is recorded, the feedback reaches the chat, and leaking feedback is replaced
- no key means no check
- progress statuses and counts
- the check is the owner student's only, and budgets and the kill switch apply

Web: the progress helpers and the request shapes.

## Open questions
- None.
