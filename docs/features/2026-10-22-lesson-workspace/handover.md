# Handover: Lesson workspace

- **Owner:** punji
- **PR:** see the PR for `feat/lesson-workspace`
- **Merged:** 2026-10-23

## What was built
The plan, with these differences:
- **No `ChatPane.tsx`.** The chat pane lives in `ChatThread.tsx`, and the composer moved out into `Composer.tsx` (with `Recipient` and `RECIPIENT_LABELS`). `ChatThread` re-exports `type Recipient`, because tests import it from there.
- **The container query is on `.lesson-layout`, not `.chat`.** The plan put it on `.chat`. But a size container may create a stacking context, and on phones `.chat` holds the *Your chats* toggle, which has to stay above the sidebar drawer. `.lesson-layout` holds only the workspace, the chat pane and the sheet button, so either way the drawer and its toggle stay on top. When a worksheet is present, `.chat:has(> .has-workspace)` drops `.chat`'s padding, so `.lesson-layout` is as wide as `.chat` and the 900 px switch point is the same as planned.
- **The sheet slides up, but closes at once.** A closing transition also played once on every page load, when the worksheet arrived and the sheet styles first applied, so the sheet visibly slid away. Only opening animates now. Under reduced motion both are instant.
- **New tokens:** `--z-sheet` (5, below the drawer's 10) and `--shadow-sheet` (an upward shadow), in light and dark.
- **The helper is `checkPlan`, not `checkAction`.** It returns `check_working`, `submit` or a `problem` message.
- **Added after browser testing:**
  - moving to another question scrolls the workspace back to the top, so *Next question →* at the bottom of a phone screen shows the new question, not its empty answer line;
  - the unread badge has a hidden ", " so screen readers say "Ask Prof AI, 2 new", not "Ask Prof AI2 new";
  - the chat pane is also a container (`pane`), and the composer stacks below 34rem of pane width. On a 1366 px screen with the sidebar, the chat is about 440 px wide.
- **Looks:** the working is ruled like an exercise book, with a margin rule (`--danger-line`) running through every line, and the answer line underlined twice. *I'm stuck* shares the `.secondary` button style.
- **Lessons page:** chat rows use `.user-row.lesson-row`. The title takes the room, and the selects and buttons wrap onto their own line (the title column went from about 60 px to about 680 px at 1366 px).

### After Punji's first test (2026-10-23)
- **Fixed: *Submit my answer* showed "Prof AI is unavailable" on harder answers.**
  - Punji gave both roots of an age question, one of them negative. Each check call allowed 300 output tokens, and reasoning tokens count towards that cap. Replaying it against Luna, marking the two roots used 138–256 tokens (up to 214 of them reasoning), so a longer question went over. The JSON reply was cut off, `parse_mark` raised, and the server returned 502.
  - The web never shows a 5xx message (`api.ts`, pinned by Sam's `api.test.ts`), so the student saw the generic "unavailable".
  - `CHECK_OUTPUT_TOKENS` is now 1,000, for both marking and hints. Only tokens used are billed, and a check still fits the 50k-a-minute quota.
- **Lines of working mix words and maths.**
  - A line starts in **words**, so "I need two numbers that add to 4 and multiply to 5" is a line of working as it stands.
  - A maths key (`=`, `+`, `^`, `/`, `*`, `<`, `>`) turns the maths typed just before it into maths and carries on in maths: `x` then `^` makes x², and "so x = 3" keeps "so" as a word.
  - A space after a real word typed in maths turns that word back into words. MathLive may already have turned some of its letters into symbols ("since" into sin), so the letters the student typed are used.
  - `"` still switches by hand, and a **Words / Maths** switch beside *Add a line* shows and sets the mode at the caret. It's there on phones, where there's no `"`.
  - Lines are still stored as `$…$` LaTeX, with the words in `\text{…}`. The marking and hint prompts now say a sentence of reasoning counts as working.
  - Words can't simply be typed in maths mode and fixed afterwards: MathLive's inline shortcuts rewrite letter pairs as you type (`th` is tanh, `mu` is μ, `in` is ∈).
- **The answer is a line you tick.** The separate answer row is gone. Each line has a ✓; the ticked line is labelled "Answer" in the margin, underlined twice, sent as the answer, and the other lines are sent as working. The button reads *Submit my answer* once a ticked line has something on it.
- ***I'm stuck* numbers lines as the student sees them,** with the given first step as line 1.
- **Two display bugs:**
  - the editor's container was `.working`, a class the "Started" status chip and question chips also carry, so the margin rule was drawn inside them as a stray bar. It's `.working-sheet` now;
  - the question text and the given step could show a vertical scrollbar for 1 px of maths, so they now only scroll sideways.

## How to run / use it
- **As a student**, open a lesson chat that has questions. On a wide screen the question and working sit on the left and the chat on the right. Below 900 px the chat is behind *Ask Prof AI* at the bottom right; Escape or × closes it.
- **Working:**
  - Write in words; type maths and it becomes maths; a space after a word goes back to words. `"` or the Words / Maths switch does it by hand.
  - Tick ✓ on the line with your answer, then *Submit my answer*.
  - Enter adds a line, Backspace on an empty line removes it, ↑ and ↓ move between lines (through MathLive's `move-out`, so arrows inside a fraction still work), and Ctrl/⌘+Enter checks. The hint about the keys is hidden on touch screens.
- **First steps:** on the Lessons page each question has a "First step (shown at Step by step)" field. *Draft first steps (N)* asks Prof AI for the questions that have none. Each draft gets a "Drafted by Prof AI" badge and *Looks right*, and *Set up chat* stays disabled until every draft is confirmed or edited. Students see first steps only when the lesson is at *Step by step*.
- **As a tutor**, open a student's chat from the Lessons page. The left pane shows that student's submitted attempts at the current question, newest first.

## Contracts other code can rely on
- `Question.first_step: str | None` (up to 300 characters) and `Question.first_step_needs_review: bool` (`chat/models.py`). `validate_lesson` tidies them and refuses a save with "Check the first steps Prof AI drafted before saving: 1, 3."
- `chat.checking.shown_first_step(lesson, question)` returns the step only at `step_by_step`. `question_reference`, `mark_request` and `working_check_request` take it, and marking and hints get it as `<given_first_step>`.
- `POST /api/lessons/first-steps`, tutors only, through `ChatService.draft_first_steps` and `_tutor_task` (kill switch, budgets, rate limit; the tutor's preferred model):
  - takes `{questions: [{number, text, answer?}]}`, at most 60;
  - returns `{first_steps: [{number, first_step | null}]}`;
  - a draft that contains the key (`leaks_key`) or is over 300 characters comes back as `null`.
- `LessonOverview.first_steps: dict[str, str]` and `ConversationDetail.attempts: list[AttemptOut]` (question, working, answer, verdict, correct, verified, at). **Both are left out of the JSON when empty** (`Field(exclude_if=...)`), so Sam's exact-shape tests still pass:
  - `tests/context_budget/test_memory_and_budgets.py::test_the_ledger_and_summary_are_not_sent_to_the_browser`;
  - `tests/lessons/test_lesson_chats.py::test_students_see_the_lesson_title_and_topics_but_never_material_or_notes`.
- **Web:**
  - `web/src/workspace.ts`: `checkPlan`, `checkLabel`, `stuckMessage`, `workingPrompt`, `attemptMarkdown`.
  - `progress.ts`: `studentStatus`. `StepInput.tsx`: `lineKey`. `api.ts`: `draftFirstSteps`, `Attempt`, `FirstStepDraft`.
  - `LessonPanel` props: `onHelp` became `onStuck`; there's a new `attempts` prop.
  - `WorkingEditor`'s `Draft` is `{steps, answerLine}`. `answerOf(draft)` is the ticked line, and `filledSteps(draft)` is the other non-empty lines.
  - `lineModes.ts`: `MATHS_KEYS`, `isWord`, `mathsTail`.
  - `StepInput` takes `onFocus`, `onModeChange` and `modeRequest` (maths fields only).
  - `stuckMessage(steps, given?)`.
- **Steps from the web may contain words** as `\text{…}` inside `$…$`. `normalise_answer` already unwraps them, so `$x=-1\text{ or }x=-5$` matches a key of `x = -1 or x = -5`.
- `CHECK_OUTPUT_TOKENS` is 1,000. Don't shrink it: reasoning tokens count towards it.
- The check button's label stays exactly *Submit my answer* once a ticked line has something on it. `chat.checking.ONLY_SUBMIT_COMPLETES`, `prompts/tutor.md`, the eval scenario and `tests/lesson_chat_bugs` all name it.
- **CSS hooks:**
  - `.lesson-layout.has-workspace[data-chat-open]`;
  - `section.workspace` and `section.chat-pane`;
  - `button.chat-sheet-button` with `.unread-badge`;
  - the containers `lesson`, `workspace` and `pane`;
  - `.working-sheet` for the editor (not `.working`, which is a status class).

## Tests added
- `tests/lesson_workspace/test_lesson_workspace.py` (10 tests):
  - first steps reach students only at *Step by step*;
  - an unconfirmed draft blocks a save;
  - only tutors can draft;
  - drafts that leak the key, or are too long, are dropped;
  - drafting respects the kill switch;
  - marking, hints and chat turns are told which line was given, and it never counts as the student's working;
  - the student and their tutor see each attempt, and no one else does;
  - marking and hints get `CHECK_OUTPUT_TOKENS` of at least 1,000, to leave room for reasoning (the 502 above).
- `web/src/lessonWorkspace.test.ts` (19 tests):
  - the check plan and label;
  - *I'm stuck*'s message;
  - working prompts by support level;
  - `studentStatus`;
  - `lineKey`;
  - the panel at *Step by step* with a first step, and at *Balanced* without;
  - tutors' attempts, newest first, and the no-answers line;
  - `attemptMarkdown`;
  - the `draftFirstSteps` request shape;
  - words or maths: `isWord` and `mathsTail`;
  - answer marking: `answerOf` and `filledSteps`, the "Answer" label, a ✓ on every line but the given one, and the hint;
  - *I'm stuck* numbering from the given first step.
- **Punji's own tests, changed because this redesign replaces what they pinned.** Each still checks the same thing:
  - `studentLessonPage.test.ts`:
    - passes `onStuck` instead of `onHelp`;
    - the done marker is now "1 of 2 done" and a `strip-correct` segment, because the question grid is closed by default ("A1.1 ✓" was a chip);
    - the empty answer line makes the button "Check my working";
    - students get "I'm stuck";
    - tutors get no "Your working", no check button and no "I'm stuck".
  - `showYourWorking.test.ts`:
    - passes `onStuck`;
    - "Step 1: write down what the question gives you" became the hint "Start by writing down what the question gives you" and the placeholder "What the question gives you";
    - "Final answer" became the ✓ on step 1 (`aria-label="Step 1 is my answer"`), because there's no answer row, and "Check my working so far" became "Check my working";
    - `filledSteps` takes `{steps, answerLine}`;
    - *Submit my answer* is checked through `checkLabel`, because the rendered answer line is empty;
    - "Can you explain the method?" is still in `HELP_PROMPTS` but no longer in the panel (it's in the chat pane's empty state);
    - stretch now also asserts "Set out your working however makes sense to you".
- No test of Sam's was changed. The suite is 363 pytest and 124 vitest, all passing.

## Known issues / TODOs
- **Tried in a local harness, not on the live app or a real phone.** The harness was the real `App` with a fake API, built with the production Vite config and served by `mount_frontend`, so the browser enforced the real CSP. It covered:
  - 1366×768, 768×1024 and 375×812, in light and dark;
  - two panes; the sheet opening, Escape and ×, with focus returning to the button;
  - the unread badge; the *Your chats* drawer staying above an open sheet;
  - MathLive's Enter, Backspace, ↑/↓ and Ctrl+Enter; the label switching to *Submit my answer*;
  - words, maths and mixed lines from real key presses, the Words / Maths switch, and ticking an answer;
  - *I'm stuck* sending the working tagged with the question; first steps and tutors' attempts;
  - the Lessons page's drafting and review gate;
  - no CSP violations or console errors.
- **Words and maths, not tried on a real phone.** Phones type through MathLive's own keyboard. In the harness, its typing commands (`insert`, `typedText`) honoured words mode, but its maths keys don't trigger the switch to maths the way a physical `^` does; use the Words / Maths switch. The `"` key couldn't be pressed by the test tool, as in the MathLive handover.
- **Switching to maths by button mid-sentence** lets MathLive take a number just before the caret into the maths ("add to 4" then Maths then x² gives 4x²). It reads correctly.
- **Words in maths mode stay maths unless a space follows:** "ok" or two-letter runs that aren't common words (xy) stay as letters, by design.
- **Tutors don't see the first step** in a student's lesson view, only on the Lessons page when setting it up.
- **Existing lessons have no first steps,** because saved lessons can't be edited yet. *Step by step* falls back to "Start by writing down what the question gives you".
- **The sheet isn't modal:** there's no focus trap or backdrop, and the workspace's top stays usable above it.
- **`prof eval dilution` wasn't re-run** (Punji's call for now). The marking and hint prompts gained a sentence about the given first step; the base tutor prompt didn't change.
- **Phase 2 will take further:** the type scale (the new text is 0.82–0.92rem), 44 px targets everywhere (most of the new buttons are about 44 px already; the × that removes a line is 34 px), and a "Your lessons" home.

## For the other dev
- **Sam:**
  - none of your tests changed;
  - `ChatRefusedError(502, …)` messages, like "Couldn't check that. Try again in a moment.", never reach the browser: `api.ts` hides every 5xx message, and your `api.test.ts` pins that. Students see "Prof AI is unavailable right now" for a reply that couldn't be read. Showing the message for 502s only would help; it's your call, so I left it;
  - `attempts` and `first_steps` are left out of the JSON when empty, specifically so your exact-shape tests hold. If you add a field to `LessonOverview` or `ConversationDetail`, that's the pattern to follow.
- **`styles.css`:**
  - `.chat` drops its padding when it holds a worksheet (`.chat:has(> .has-workspace)`);
  - the old `.lesson-panel`, `.question-card`, `.help-buttons`, `.working-steps`, `.thread-filter` and related rules are gone;
  - `.step-input` fields are now borderless, because the ruled line is the field.
- **Changing the lesson layout:** use the `lesson` container query, not a viewport media query. The student page has a sidebar and the tutor's doesn't.
