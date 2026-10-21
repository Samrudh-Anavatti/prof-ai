# Handover: Lesson chat bugs

- **Owner:** sam
- **PR:** see the PR for `fix/lesson-chat-bugs`
- **Merged:** 2026-10-21

## What was built
The three bugs Punji logged, fixed as planned:
1. **Prof AI no longer finishes questions.** Every turn tagged with a question now tells Prof AI that only *Submit my answer* marks it done: it can say a step or answer looks right, then tells the student to submit, and doesn't start another question (`chat.checking.ONLY_SUBMIT_COMPLETES`, appended by `question_reference`). The base prompt's boundaries say the same in one line, for untagged turns.
2. **The thread follows the current question.** In a lesson with questions, the thread shows the current question's messages plus untagged ones (general chat belongs to every question). A bar above the thread says which question it's showing, with *Show all questions* / *Only question N*. Prof AI's replies are now saved with their message's `question`; replies saved before this fix are matched to the message they answer.
3. **A tutor trying a lesson on themselves gets the student controls.** The chat's owner gets Prof AI by default in a lesson chat (`asks_ai`'s new `owner_author`), so the tutor no longer needs `@AI` there. On the web, `ChatThread`'s `own` prop (set on the chat page, where every chat is the viewer's own) decides the working editor, help buttons, *Submit my answer* and the *Ask Prof AI* button. *Send to tutor only* stays for students.

Also: the eval has a new `premature-done` case (16 in all), and `Scenario` takes an optional `question` that reaches the model as the app sends it.

## How to run / use it
- Open a lesson with questions as a student, ask about question 1, switch to question 2: the thread shows only question 2's messages (plus untagged ones). *Show all questions* shows everything.
- As a tutor, set up a lesson for yourself on the Lessons page and open it from the chat page: you get the working editor, help buttons and *Submit my answer*, and Prof AI answers without `@AI`.
- `prof eval dilution` (dry run) lists the new case; `--yes` runs it.

## Contracts other code can rely on
- `asks_ai(conversation, content, author="student", to_tutor=False, owner_author="student")`: in a lesson chat, `author == owner_author` gets Prof AI unless `to_tutor`. `ChatService.begin_turn` passes the owner's author. `asksAi(shared, author, content, toTutor?, ownerAuthor?)` mirrors it.
- Prof AI's reply to a message tagged with a question carries the same `question`.
- `ChatThread` prop `own?: boolean` (default false): the viewer works the questions.
- `messagesForQuestion(messages, question)` in `web/src/progress.ts`.
- `ONLY_SUBMIT_COMPLETES` in `chat/checking.py`; eval `Scenario.question: Question | None`.

## Tests added
- `tests/lesson_chat_bugs/`: the question reference and base prompt say only submitting completes a question; a reply is saved with its question; a tutor's own lesson chat gets Prof AI without `@AI`; a tutor in a student's chat still needs `@AI`; the `premature-done` case sends its question with the turn.
- `web/src/lessonChatBugs.test.ts`: `asksAi` with an owner; `messagesForQuestion` keeps untagged messages, keeps old untagged replies with their message, and shows only untagged ones for an untouched question.
- No existing test changed.

## Known issues / TODOs
- **Not tried in a browser or against Luna.** The `ChatThread` controls aren't render-tested (it loads in an effect and the web tests run without a DOM), so please check bug 3's fix on the live app. Bug 1's fix is a prompt change: run `prof eval dilution --yes` to see `premature-done` pass. It also covers the base prompt changes from Punji's features, which still need a run.
- The filter follows the question the viewer has open, so a tutor reading a student's chat sees the student's current question first; *Show all questions* shows the rest.

## For the other dev
- Punji: your three logged bugs are fixed here; the INDEX rows now point to this feature.
- New lesson chat UI should use `own`, not the viewer's role, to decide who works the questions.
