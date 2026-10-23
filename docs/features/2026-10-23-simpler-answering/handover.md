# Handover: Simpler answering

- **Owner:** punji
- **PR:** see the PR for `fix/simpler-answering`
- **Merged:** 2026-10-23

## What was built
As planned. Answering is now two buttons:
- **Submit my answer** marks the working. The last line with something on it is the answer, and the lines before it are the working. With nothing written, it says "Write your working, with your answer on the last line." Ctrl/⌘+Enter does the same.
- **I'm stuck** checks the working so far (`check_working`): the hint shows under the working and in the chat as "I'm stuck. Here's my working so far: …". With nothing written yet, it sends "I'm stuck. How do I start?" (or "How do I carry on from the first step?") to Prof AI and opens the chat.
- **Gone:** *Check my working*, the ✓ on each line, and the "Answer" line.
- The hint above the working ends "Write in words or maths. Your last line is your answer."

## How to run / use it
Open a lesson question, write your working with the answer on the last line, and press *Submit my answer*. Press *I'm stuck* at any point for a hint on where you are.

## Contracts other code can rely on
- `web/src/WorkingEditor.tsx`: `Draft` is `{steps}`. `filledSteps(draft)` is every non-empty line.
- `web/src/workspace.ts`: `submission(lines)` gives `{working, answer}` (the answer is the last line), or `null` when nothing is written. `checkPlan` and `checkLabel` are gone.
- `ChatService.check_working` records the student's side as "I'm stuck. Here's my working so far:" followed by the numbered working. The endpoints are unchanged.
- The submit button's label is always exactly *Submit my answer*.

## Tests added
- `tests/lesson_workspace/`: a working check shows in the chat as "I'm stuck…", tagged with the question.
- `web/src/lessonWorkspace.test.ts`:
  - `submission`;
  - `filledSteps` counts only lines with something on them;
  - students get *Submit my answer* and *I'm stuck* and the "last line" hint, and no *Check my working*;
  - the editor has no answer line or tick.
  The tick and *Check my working* tests are gone with the features.
- **Punji's own tests, updated for the two buttons:**
  - `studentLessonPage.test.ts` checks *Submit my answer* again, as it did before the lesson workspace;
  - `showYourWorking.test.ts` checks the "last line" hint, *I'm stuck* and *Submit my answer*, and `filledSteps` takes `{steps}`.
- The suite is 364 pytest and 122 vitest, all passing.

## Known issues / TODOs
- A student who writes past their answer submits the last line, not their answer. Marking catches it as a wrong answer.
- In the chat, a line written in words shows in the maths font, because it's stored as `$\text{…}$`.

## For the other dev
- Sam: nothing needed. None of your tests changed.
