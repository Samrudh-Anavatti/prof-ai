# Plan: Lesson chat bugs

- **Owner:** sam
- **Branch:** `fix/lesson-chat-bugs`
- **Date:** 2026-10-21

## Goal
Fix the three lesson-chat bugs Punji logged in `INDEX.md` on 2026-10-22:
1. Prof AI tells a student an answer is "exactly right" and moves on, but the question isn't marked done. Only *Submit my answer* completes a question.
2. Switching questions on the lesson page doesn't change the chat: every question's messages show together.
3. A tutor trying a lesson in their own chat gets the tutor view (no working editor, help buttons or *Submit my answer*), and every message needs `@AI`.

## Approach
1. **Prof AI doesn't finish questions.** `chat.checking.question_reference` (sent with every turn tagged with a question) says Prof AI may say a step or answer looks right but can't mark the question done: only *Submit my answer* does. When the student seems finished, it tells them to submit their working and final answer, and it doesn't start another question. The base prompt's lesson rule says the same in one line, for untagged turns. A new eval case, `premature-done`, carries a question reference; the eval's `Scenario` gains an optional `question` for that.
2. **The thread follows the current question.** In a lesson with questions, the thread shows messages tagged with the current question plus untagged ones (general chat, which belongs to every question), with a *Show all questions* toggle. Prof AI's normal replies are now saved with their message's `question` (submissions and working checks already were); for older replies, the web treats an untagged Prof AI reply as belonging to the message it answers.
3. **The chat's owner gets the solver's view.** `asks_ai` gains `owner_author` (default `"student"`): the owner of a lesson chat gets Prof AI by default, and someone else in it (the student's tutor) asks with `@AI`. In student chats nothing changes. On the web, `ChatThread` takes `own` (true on the chat page, where every chat is the viewer's own; false on the tutor's view of a student's chat), and the working editor, help buttons, *Submit my answer* and *Ask Prof AI* follow `own` rather than the viewer's role. *Send to tutor only* stays for students only.

## Risks
- **R4 answer leaks:** the new wording in `question_reference` doesn't change how the key is handled; it still says never reveal it. The leak guards on marking are untouched.
- **R2 / scope:** the base prompt grows by one line; `check_budget` still has to pass (base plus the largest support level under the base cap). Tested by the existing startup check.
- **Cost:** tutors' own lesson chats now call Prof AI without `@AI`. Tutors are exempt from the per-user budget but still inside the global budget, kill switch and rate limit, and they're only trying lessons.
- **Hidden messages:** filtering could hide a tutor's message from a student. Untagged messages show under every question, tagged ones show under their question, and *Show all questions* shows everything.
- **Child safety, data:** no change.

## Learning check
- **L3 retrieval practice** and the show-your-working loop depend on the student submitting; bug 1 had Prof AI short-circuit that. The fix sends students back to *Submit my answer*.
- Showing one question's conversation at a time keeps attention on the current problem (less split attention), without losing the rest.

## Files / modules touched
- `src/prof_ai/chat/checking.py`, `src/prof_ai/chat/prompts/tutor.md`, `src/prof_ai/chat/service.py`
- `src/prof_ai/evals/dilution.py`, `src/prof_ai/evals/scenarios.json`
- `web/src/ChatThread.tsx`, `web/src/ChatPage.tsx`, `web/src/progress.ts`, `web/src/styles.css`

## Contracts added or changed
- `asks_ai(conversation, content, author="student", to_tutor=False, owner_author="student")`; `asksAi(shared, author, content, toTutor?, ownerAuthor?)` mirrors it.
- Prof AI's replies to a tagged message carry the same `question`.
- `ChatThread` prop `own?: boolean`.
- `messagesForQuestion(messages, question)` in `web/src/progress.ts`.
- Eval `Scenario.question` (optional `{number, text, answer}`).

## Tests to add
Under `tests/lesson_chat_bugs/` and `web/src/lessonChatBugs.test.ts`:
- the question reference says only *Submit my answer* completes a question, and the base prompt says it too;
- a reply to a tagged message is saved with that question;
- a tutor's own lesson chat gets Prof AI without `@AI`, and the tutor still needs `@AI` in a student's chat;
- the `premature-done` scenario loads and its question reaches the context;
- web: `asksAi` with an owner; `messagesForQuestion` keeps untagged and inherits replies; the tutor's own lesson chat shows the student controls, the tutor's view of a student's chat doesn't.

## Open questions
- None blocking. The eval should be re-run (Punji's handovers already ask for it).
