# Plan: Lesson workspace

- **Owner:** punji
- **Branch:** `feat/lesson-workspace`
- **Date:** 2026-10-22

## Goal
Make answering questions the main thing on the lesson screen. A review at 1366×768 (the usual school Chromebook) found:
- the chat thread gets 38 px, so no messages show;
- the worked examples collapse to 22 px, even when opened;
- on a phone, the question sits under four rows of chips and the page and panel scroll separately;
- the working editor is misaligned;
- the help buttons repeat on every question;
- tutors can't see what a student submitted.

## Approach
- **Two panes.** On wide screens, the question and working go on the left (about 60%) and the chat on the right. Each pane scrolls on its own. Below 900 px of chat width (phones, iPad portrait), it's one column, and the chat is a sheet that slides up from an *Ask Prof AI* button showing an unread count. A container query on `.chat` decides this, so a page with a sidebar and one without both get it right. Lessons without questions keep today's single chat column.
- **Question navigation.** "Question 2 of 28", previous and next, a thin progress strip, and a grid to jump to any question. Students see Not started / Started / Done. Tutors keep tries and help counts.
- **The question.** Larger type. Worked examples sit above it, opened at *Step by step*, not in a nested scroll box.
- **Working lines.**
  - Ruled lines with numbers aligned to them, a quiet *Add a line* row, and the answer as the last ruled line.
  - Enter adds a line, Backspace on an empty line removes it, ↑/↓ move between lines (through MathLive's `move-out` event, so arrows inside a fraction still work), and Ctrl/⌘+Enter checks.
  - A hint line says so, hidden on touch screens.
- **Prefilled by support level.**
  - *Step by step* shows the question's `first_step` as a read-only first line ("Started for you"), and the student carries on from it.
  - *Balanced* prompts "Start with what you know".
  - *Stretch* says "Set out your working however makes sense to you".
  - Without a first step, *Step by step* falls back to "Write down what the question gives you".
- **First steps.**
  - On the Lessons page, *Draft first steps* asks Prof AI for one per question. Each draft is marked for review, and the lesson can't be saved until the tutor confirms it (the same gate as worked-out answers). The tutor can also type or edit one.
  - The server drops any draft that contains the question's answer.
  - The server only sends first steps to a student's browser at *Step by step* (`LessonOverview.first_steps`). Marking and hints are told which line was given, so it never counts as the student's own working.
- **One check button.**
  - It reads "Check my working" while the answer line is empty, which gives a hint and doesn't count as a try.
  - It reads "Submit my answer" once there's an answer, which marks it. "Submit my answer" keeps Prof AI's prompt and Sam's tests correct.
  - An answer with no working gets the server's existing "show your working" refusal, with no model call. Nothing written gets "Write a line of working first" without calling the server.
  - The button is never disabled; it explains instead.
- **Help.** *I'm stuck* sends "I'm stuck" plus the student's current working to Prof AI, tagged with the question, and opens the chat. The three canned prompts move to the chat pane's empty state.
- **Feedback.** It appears under the working, with *Next question* after a correct answer.
- **Tutor view of a student's lesson.** The same two panes. The left shows the student's attempts at the current question: working, answer, verdict and time, newest first. `ConversationDetail.attempts` carries them.
- **Lessons page.** Fix the chat rows that squeeze the title column to about 60 px.

## Risks
- **R4 (answers reach students).**
  - First steps are student-visible. Prof AI's drafts that contain the answer are dropped (`leaks_key`), and every draft needs the tutor's confirmation before the lesson saves.
  - A tutor's own first step isn't checked: a short numeric key would give false alarms, and it's the tutor's content.
  - Answers stay out of `LessonOverview`.
- **Correctness.** A wrong first step misleads a beginner. The tutor review gate controls this, and drafts follow the solve prompt's rules (null when unsure, ignore instructions inside questions).
- **Cost.** *Draft first steps* is one tutor-side call through `ChatService._tutor_task` (kill switch, budgets, rate limit), capped at 4,000 output tokens and charged to the tutor. *I'm stuck* is an ordinary chat turn. No new student-side model calls.
- **Abuse.** The drafting endpoint is tutor-only. *I'm stuck* goes through the normal message pipeline with its caps.
- **Data.**
  - Attempts are the student's own working, already stored. They go to the chat's owner and their tutor, the same people who can read the chat.
  - No new per-user data, so `user_data_eraser` doesn't change.
  - The payload grows by at most 60 questions' attempts; the detail only reloads when the chat changes.
- **Child safety.** No new channel. Help still goes through the guarded chat.

## Learning check
- **Applies L1/L2.** Completion problems: support fades from a given first step to a blank page (van Merriënboer; Renkl & Atkinson, 2003).
- **Applies L7.** *I'm stuck* sends the current working, so the hint is about the student's step.
- **Applies L8.** One question in view, help tucked away, and the chat beside the question rather than squeezed under it.
- **Applies L11.** Help counts are no longer on the student's screen, where they discourage asking. Help is one click away but not permanently on display, which invites less hint-farming.
- **Works against nothing we know of.** Students lose the attempt count, but they still see Started/Done.

## Files / modules touched
- `src/prof_ai/chat/models.py`, `chat/api.py`, `chat/checking.py`, `chat/service.py`, `chat/prompts/mark_working.md`, `chat/prompts/check_working.md`
- `src/prof_ai/lessons/rules.py`, `lessons/api.py`, `lessons/first_steps.py` (new), `lessons/prompts/first_steps.md` (new)
- `web/src/ChatThread.tsx`, `ChatPane.tsx` (new), `LessonPanel.tsx`, `QuestionNav.tsx` (new), `WorkingEditor.tsx`, `StepInput.tsx`, `progress.ts`, `api.ts`, `LessonsPage.tsx`, `styles.css`

## Contracts added or changed
- `Question.first_step: str | None` (up to 300 characters) and `Question.first_step_needs_review: bool`. `validate_lesson` refuses a save while any draft is unconfirmed.
- `LessonOverview.first_steps: dict[str, str]`, keyed by question number, only at *Step by step*.
- `ConversationDetail.attempts: list[AttemptOut]` (question, working, answer, verdict, correct, verified, at).
- `POST /api/lessons/first-steps`, tutors only:
  - takes `{questions: [{number, text, answer?}]}`, at most 60;
  - returns `{first_steps: [{number, first_step | null}]}`.
- `question_reference`, `mark_request` and `working_check_request` take the shown first step.
- Web helpers: `checkAction`, `checkLabel`, `stuckMessage`, `studentStatus`, `workingPrompt`.

## Tests to add
- `tests/lesson_workspace/`:
  - first steps reach students only at *Step by step*;
  - unconfirmed drafts block a save;
  - drafting is tutor-only and drops leaking drafts;
  - marking and hints are told the given line;
  - attempts appear in the detail for the student and their tutor, and not for anyone else.
- `web/src/lessonWorkspace.test.ts`: the check action and label, the "I'm stuck" message, student status, working prompts by level, and the workspace markup for students and tutors.
- Your own `studentLessonPage.test.ts` and `showYourWorking.test.ts` pin text this redesign replaces on purpose. I'll update those assertions to the new behaviour, keep what each one checks, and list them in the handover.

## Open questions
- Saved lessons can't be edited yet, so existing lessons get the fallback prompt rather than a first step.
