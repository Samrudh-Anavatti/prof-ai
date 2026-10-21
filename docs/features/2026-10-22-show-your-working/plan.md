# Plan: Show your working

- **Owner:** punji
- **Branch:** `feat/show-your-working`
- **Date:** 2026-10-22

## Goal
A question is done when the student shows working that gets to the right answer, not when they type the answer. Today a student can paste a final answer from anywhere, an exact match is marked right for free, and nobody sees how they got there.

Now:
- The student writes their working step by step.
- They can ask Prof AI to check it at any point.
- They submit their working and final answer for a verdict.
- The tutor sees every attempt's working.

If a question has no answer key, the tutor can have Prof AI work one out and confirm it before saving.

## Approach
**Answering (student's lesson page):**
- **Working:** a list of steps, one line each. Steps are typed maths such as `2x + y = 13`, `x^2`, `3/4` or `sqrt(10)`, or plain words. Each line is typeset live underneath it (`web/src/typedMaths.ts` converts the line to LaTeX; the existing KaTeX `Markdown` draws it).
  - *Add a step* or Enter starts a new line.
  - At *Step by step*, the first line's placeholder suggests a starting point.
  - The input is one component (`StepInput.tsx`), so MathLive can replace it later. That needs a security-policy change Sam has to agree to.
- **Final answer:** one line, previewed the same way.
- **Check my working so far:** Prof AI reads the partial working. It says the student is on track (and nudges towards the next step without doing it), or points to the first wrong step with a hint. It's recorded in the chat as help for that question, and doesn't mark anything.
- **Submit** (working and answer) gets one of four verdicts:

  | Verdict | When | Done? |
  |---|---|---|
  | `correct` | Right answer, and the working reaches it with a valid method | ✓ |
  | `show_working` | Right answer, but the working is missing or doesn't lead to it | |
  | `slip` | Right method, with a mistake in one step | |
  | `not_yet` | Wrong method, or stuck | |

  On `correct`, a *Next question* button appears. Navigation stays open: students can move between questions freely.
- **The working is kept per question** while the student moves between questions, and cleared once the question is correct.
- **Help buttons:** "Can you check my working so far?" is replaced by "Can you explain the method?", because checking the working now has its own button.

**Marking (server):**
- **A free floor first:**
  - Working that's empty, or only repeats the answer, is refused with no model call.
  - Limits: 30 steps of up to 300 characters each, and an answer of up to 500 characters.
- **Every submission goes to the model** (`chat/prompts/mark_working.md`). It gets the question, the key, the numbered steps, the answer, and whether the answer matches the key exactly.
  - It returns `{verdict, feedback}`.
  - An exact match can only be `correct` or `show_working`: a `slip` or `not_yet` verdict on an exact match becomes `show_working`.
- **No key:** the model judges the working and answer alone, and the attempt is stored as unverified, so the tutor sees it was marked without a key.
- **Leak guard:** feedback on anything but `correct` is replaced with neutral text for that verdict if it contains the key. Working-check feedback is always guarded.
- **Model:** the chat's approved model (`_engine_for`), with budgets, kill switch and rate limit, charged to the student. The kill switch now stops every check, because an exact match alone no longer marks a question.
- **Recording:**
  - Each submission adds an `Attempt` (question, working, answer, verdict, verified, at) and the exchange to the chat (`checks_answer=True`).
  - Each working check adds a tagged exchange, which counts as a help message.
- **Progress** gains `last_verdict` and `unverified`.

**Missing answers (tutor's question review):**
- *Work out missing answers (n)* sends the questions without an answer to `POST /api/lessons/answers`, through `ChatService.solve_questions` (`_tutor_task`; the tutor's preferred model, since questions are tutor content).
- The prompt (`lessons/prompts/solve_questions.md`) gives final answers only, in LaTeX, and null where it can't (for example, a missing diagram).
- **Review before saving:**
  - Answers come back with `answer_needs_review=True`, shown with a "Worked out by Prof AI" badge and a *Looks right* button. Editing the answer also clears the flag.
  - `validate_lesson` refuses to save a question whose answer still needs review, so a student is never checked against an answer the tutor hasn't seen.

## Risks
- **R4 (answers handed over):**
  - The key never goes to the student. Every feedback path is leak-guarded.
  - The working-check prompt forbids doing the next step for them.
  - Missing answers are worked out only on the tutor's request, and are never sent to a student.
- **R7 (unfair or wrong marking):**
  - The model now judges working as well as the answer, so marking depends more on the model. Controls:
    - every attempt's working, verdict and feedback is stored and shown to the tutor;
    - an exact match can't be marked wrong (at worst *show your working*);
    - no-key marks are labelled unverified.
  - The tutor still can't override a verdict (later).
- **R15 (generated answers wrong):** answers Prof AI works out need the tutor's *Looks right*, enforced on save.
- **R3 (cost):** every submission is now a model call, about 1.5k tokens in and 300 out, roughly $0.0008 on Luna. Each check is also bounded by the rate limit and the student's daily budget. Solving missing answers is a single call of up to 3,000 output tokens, charged to the tutor.
- **R18 (CSP):** unchanged. Typeset previews use the existing MathML path. MathLive would need `style-src-attr 'unsafe-inline'`, which goes against Sam's `test_shell_has_strict_security_headers`; it's left for Sam to decide (handover).
- **R23 (prompt injection in working):** the steps and answer are wrapped as data. The prompt says to ignore instructions in them and to judge them as working.
- **Child safety:** working text is student input, so a content-filter hit is flagged on the chat (as for checks today) and returns the safe filtered message.
- **Failure:** an unreadable model reply gives a 502 with "try again", and nothing is recorded.

## Learning check
- **L3 retrieval practice, L5 productive struggle:** the student has to produce the method, not just an answer.
- **L4 useful feedback:** the verdict says what kind of problem it is (missing working, a slip, the method), and the feedback names the step.
- **L7 step-based hints:** *Check my working so far* helps at the step where the student is, inside the question.
- **L11 gaming:** pasting an answer no longer completes a question. Nothing is detected or locked; the tutor sees the working.

## Files / modules touched
- **Python:**
  - `chat/models.py` (`Attempt`, `Question.answer_needs_review`)
  - `chat/checking.py` (verdicts, floor, requests, parsing, progress)
  - `chat/prompts/mark_working.md` and `check_working.md` (replacing `check_answer.md`)
  - `chat/service.py`, `chat/api.py`
  - `lessons/worksheet.py` (solving), `lessons/prompts/solve_questions.md`, `lessons/rules.py`, `lessons/api.py`
- **Web:**
  - `api.ts`, `typedMaths.ts` (new), `StepInput.tsx` (new), `WorkingEditor.tsx` (new)
  - `LessonPanel.tsx`, `ChatThread.tsx`, `ChatPage.tsx`, `LessonsPage.tsx`, `progress.ts`, `styles.css`
- **Docs:** ADR 0006 amendment, CLAUDE.md, README, INDEX, risks (R4, R7, R15), learning science

## Contracts added or changed
- `Attempt`: `+working: list[str]`, `+verdict: Verdict | None`, `+verified: bool`; `correct` stays (`verdict == "correct"`).
- `Question.answer_needs_review: bool` (tutor-only; must be false to save).
- `QuestionProgress`: `+last_verdict`, `+unverified`.
- **`POST /api/chat/conversations/{id}/check`:**
  - body: `{question, working: [str], answer}` (was `{question, answer}`)
  - returns: `{verdict, correct, feedback, progress}`
- **`POST /api/chat/conversations/{id}/working`:** body `{question, working}` returns `{feedback, progress}`.
- **`POST /api/lessons/answers`:** body `{questions: [{number, text}]}` returns `{answers: [{number, answer | null}]}`.
- `ChatService.submit_answer`, `ChatService.check_working`, `ChatService.solve_questions`.
- **Web:**
  - `checkAnswer(id, question, working, answer)`, `checkWorking`, `solveQuestions`
  - `typedToLatex`
  - `StepInput` props: `value`, `onChange`, `onEnter`, `placeholder`, `label`

## Tests to add
Under `tests/show_your_working/`:
- The floor refuses empty or answer-only working without a model call.
- Each verdict is returned and recorded with its working.
- An exact match can't be marked `slip` or `not_yet`.
- Leaking feedback is replaced for each verdict and for working checks.
- A no-key submission is marked and stored unverified.
- A working check is recorded as help, not an attempt.
- The kill switch stops checks.
- Only the owner can submit or check.
- Solving missing answers: tutors only, the preferred model may be unapproved, unknown numbers are dropped.
- Saving refuses answers that still need review.

My earlier `tests/student_lesson_page/` tests for the old `{question, answer}` check and the free exact match change to the new contract.

In `web/src/showYourWorking.test.ts`:
- the typed-maths conversion;
- the request shapes;
- the panel's working editor for students and none for tutors.

## Open questions
- Should a tutor be able to override a verdict? It's not in this feature.
- MathLive, once Sam has decided on the policy change.
