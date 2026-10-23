# Plan: Simpler answering

- **Owner:** punji
- **Branch:** `fix/simpler-answering`
- **Date:** 2026-10-23

## Goal
Answering a question took too much explaining. The student had to tick ✓ the line with their answer, and one button changed between *Check my working* and *Submit my answer*. Punji worked a question to the end, pressed the button and got a hint instead of a mark. Make it two plain buttons:
- **Submit my answer** marks the working. The last line is the answer.
- **I'm stuck** checks the working so far and gives a hint on the step the student is at. With nothing written yet, it asks Prof AI how to start.

A student only wants their working checked when they're submitting or stuck, so *Check my working* goes.

## Approach
- **Web:**
  - `WorkingEditor` drops the ✓ and the answer line, so its draft is just `{steps}`;
  - `workspace.submission(lines)` sends the last line as the answer and the lines before it as working;
  - `LessonPanel` shows both buttons: *I'm stuck* calls `check_working` when something is written, and otherwise sends "I'm stuck. How do I start?" to the chat;
  - Ctrl/⌘+Enter submits.
- **Server:** the hint exchange in the chat reads "I'm stuck. Here's my working so far:" (it said "Can you check my working so far?"), so it matches the button. The endpoints and their contracts don't change.

## Risks
- **Correctness:**
  - a student who carries on after their answer submits the wrong last line. The hint says "Your last line is your answer", and the marking says what to look at;
  - one line alone has no working, so the server's existing "Show your working first" refusal applies, with no model call.
- **Cost:** *I'm stuck* with working is one `check_working` call, as *Check my working* was. With nothing written it's one chat turn, as before. No new calls.
- No change to abuse, data or child safety.

## Learning check
- **Applies L7:** *I'm stuck* hints at the student's own step.
- **Applies L5:** help comes when they ask for it, after trying.
- Works against nothing.

## Files / modules touched
- `web/src/WorkingEditor.tsx`, `LessonPanel.tsx`, `workspace.ts`, `styles.css`
- `src/prof_ai/chat/service.py` (the chat text of a working check)
- `CLAUDE.md`, docs

## Contracts added or changed
- `Draft` is `{steps}`. `answerOf` and `answerLine` are gone.
- `workspace.submission(lines)` replaces `checkPlan` and `checkLabel`.
- The chat text of a working check starts "I'm stuck. Here's my working so far:".

## Tests to add
- **Web:** `submission`; both buttons and the "last line" hint; no answer line or tick in the editor.
- **Server:** a working check shows in the chat as "I'm stuck…".
- Update Punji's own tests that named *Check my working* or the tick.

## Open questions
- None.
