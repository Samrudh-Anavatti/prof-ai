# Handover: Show your working

- **Owner:** punji
- **PR:** see the PR for `feat/show-your-working`
- **Merged:** pending

## What was built
As planned, with typed steps instead of MathLive (see the decision for Sam below).

**Student's lesson page:**
- **Working:** the one-line answer box is replaced by numbered steps.
  - Students type maths the calculator way (`x^2`, `3/4`, `sqrt(10)`, `2*3`, `<=`). Each line is typeset live underneath it, and runs of words stay as text ("add them: 2x = 14").
  - Enter or *Add a step* adds a line, and × removes one.
  - At *Step by step*, the first line suggests "write down what the question gives you".
- **Final answer:** one line, previewed the same way.
- **Check my working so far:** a hint on unfinished working. It either says the student is on track and nudges them on, or names the first wrong step. Nothing is marked; it's recorded in the chat as help for that question.
- **Submit my answer:** returns one of four verdicts, each shown with a heading:
  - **Correct ✓**, with a *Next question* button;
  - **Show your working**;
  - **Nearly: check your steps**;
  - **Not yet**.
- **Working is kept per question** while the student moves between questions, and cleared once the question is correct.
- **Help buttons:** "Can you check my working so far?" became "Can you explain the method?".

**Marking:**
- **A free floor:** empty working, working that only repeats the answer, more than 30 steps, or a step over 300 characters is refused with no model call.
- **Then the model marks it** (`chat/prompts/mark_working.md`). It sees the question, the key, the numbered steps, the answer, and whether the answer matches the key exactly.
- **Guards:**
  - An exact match can't come back as `slip` or `not_yet`; it becomes `show_working`.
  - Feedback that contains the key is replaced with fixed text for its verdict. Working-check feedback is always guarded.
- **No key:** the model marks without one, and the attempt is stored unverified. The tutor's progress label then adds "marked without an answer key".
- **The free exact-match path is gone,** so the kill switch now stops every check.

**Tutor's question review:**
- **Work out missing answers (n)** sends every question without an answer to the model, using the tutor's preferred model.
- Answers come back with a "Worked out by Prof AI" badge and a *Looks right* button. Editing the answer also clears the badge.
- *Set up chat* stays disabled until each one is checked, and `validate_lesson` refuses to save any that aren't.

## How to run / use it
- **As a tutor:** set up a lesson with questions. If some lack answers, press *Work out missing answers*, check each one, then save.
- **As the student:** open the lesson, type working in the steps, try *Check my working so far*, then *Submit my answer*. Try a correct answer with no real working: it should come back as *Show your working*.

## Contracts other code can rely on
- **`Attempt`:** adds `working: list[str]`, `verdict: Verdict | None` (None for attempts saved before this change) and `verified: bool`. `correct` stays, and is `verdict == "correct"`.
- **`Verdict`:** `correct | show_working | slip | not_yet` (`chat/models.py`).
- **`Question.answer_needs_review`:** must be false to save.
- **`QuestionProgress`:** adds `last_verdict` and `unverified`.
- **`chat/checking.py`:** `tidy_working`, `missing_working`, `mark_request`, `working_check_request`, `parse_mark`, `parse_working_check`, `working_message`, `FEEDBACK`, `KEEP_GOING`. The old `check_request`, `parse_check`, `CORRECT`, `NOT_YET` and `NO_KEY` are gone.
- **`ChatService`:**
  - `submit_answer(owner, chat_id, question, working, answer) -> CheckResult(verdict, feedback, conversation)`
  - `check_working(...) -> WorkingFeedback`
  - `solve_questions(tutor, questions) -> [SolvedAnswer]`
  - `check_answer` is gone.
- **API:**
  - `POST /api/chat/conversations/{id}/check`: body `{question, working, answer}`, returns `{verdict, correct, feedback, progress}`.
  - `POST /api/chat/conversations/{id}/working`: body `{question, working}`, returns `{feedback, progress}`.
  - `POST /api/lessons/answers`: body `{questions: [{number, text}]}` (at most 60), returns `{answers: [{number, answer | null}]}`.
- **Web:**
  - `checkAnswer(id, question, working, answer)`, `checkWorking`, `solveQuestions`
  - `typedToLatex` and `stepPreview` (`typedMaths.ts`)
  - `StepInput`, `WorkingEditor`, `VERDICT_LABELS`
  - `LessonPanel`'s `onCheck(number, working, answer)` and `onCheckWorking`

## Tests added
- **`tests/show_your_working/`:**
  - the floor, with no model call;
  - each verdict returned and recorded with its working;
  - what the marking prompt contains, and that the student pays;
  - an exact match is never marked wrong;
  - leaking feedback is replaced for each verdict and for working checks;
  - no-key marking is unverified;
  - a working check counts as help, not an attempt;
  - unreadable marks record nothing;
  - the kill switch;
  - owner-only access;
  - solving missing answers: tutors only, the preferred model, unknown numbers dropped, and the tutor is charged;
  - saving refuses unchecked answers.
- **`web/src/showYourWorking.test.ts`:**
  - the typed-maths conversion;
  - every kind of step typesets without a KaTeX error;
  - the editor for students, and none for tutors;
  - the unverified label;
  - the request shapes.
- **Changed (mine):**
  - `tests/student_lesson_page/` lost its tests of the old `{question, answer}` check and the free exact match. They're replaced by the ones above. Its progress test now submits working and expects the two new progress fields.
  - `web/src/studentLessonPage.test.ts` follows the new `checkAnswer` signature and the *Submit my answer* label.

## Known issues / TODOs
- **Not tried end to end with a real model.** The marking prompt hasn't been through `prof eval dilution` either. Worth adding cases there: a correct answer with no working, a slip, and an answer pasted with fake working.
- **The typed-maths preview is simple:**
  - Two-letter words such as "of" or "by" show as maths letters.
  - `a/b` only becomes a fraction for single terms or bracketed groups.
  
  It's only a preview: the model reads what was typed.
- **Tutors can't override a verdict yet.**
- **The working box is part of the lesson panel,** which is capped at 60% of the chat column and scrolls. On a phone that's a fair amount of scrolling.

## For the other dev
- **Decision for Sam (with Punji): the security policy for MathLive.** MathLive gives Desmos-style input: `x^2` turns into a superscript as you type, and phones get a maths keyboard. It was tried against our exact CSP:
  - It positions maths with inline `style=""` attributes, which `style-src 'self'` blocks, so fractions and roots render broken.
  - With `style-src-attr 'unsafe-inline'` added, it rendered correctly with no console errors.
  - That would change `test_shell_has_strict_security_headers`, which asserts `"unsafe-inline" not in csp`. So it wasn't done.

  **The case for it:**
  - It allows inline style attributes only. Inline scripts and `<style>` blocks stay blocked.
  - Anything a style loads (`url(...)`) is still limited to our own site.
  - Injecting HTML is still prevented by React and the lint rule.

  **The case against:**
  - It loosens R18.
  - It adds about 230 KB of script (compressed, lazy-loaded on lesson pages) and 300 KB of fonts.

  **If you agree,** the swap is `web/src/StepInput.tsx` alone: steps become `$…$` LaTeX strings, which `stepPreview`, the server and the chat already accept.
