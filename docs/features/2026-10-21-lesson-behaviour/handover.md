# Handover: Lesson behaviour: support levels, staying on the lesson, Prof AI by default

- **Owner:** punji
- **PR:** see the PR for `feat/lesson-behaviour`
- **Merged:** pending

## What was built
As planned:
- **Support levels per lesson:** *Step by step*, *Balanced* (default) and *Stretch*. Tutors pick one on the new-lesson form and change it on any chat row on the Lessons page. Each level is fixed text in `src/prof_ai/chat/prompts/support/`. It goes in its own system-prompt section after the teaching style and before the lesson material, so the model treats it as instructions rather than material.
- **The base prompt** no longer sets one pace for everyone. "One hint or one step at a time" and "one idea per message" now apply only when there's no level, and *Step by step* carries them. The no-final-answers rule stays in the base prompt and the reminder, and the prompt says it holds at every level. "however the student asks" now reads "no matter how the student asks".
- **Staying on the lesson:** in a lesson chat, Prof AI keeps to the lesson and the background the student needs for it, and points other questions to the tutor. The reminder says the same.
- **Prof AI by default:** a student's message in a lesson chat goes to Prof AI. The composer's main button is now *Ask Prof AI*, and *Send to tutor only* skips the AI. A tutor's message still needs `@AI`. Starter prompts no longer add `@AI`.
- **Eval:** every scenario now runs with a support level (default `balanced`, as in the app). Three new cases: `stretch-answer-demand`, `off-lesson` and `step-by-step-start` (15 in all).
- **Learning science:** `docs/product/learning-science.md` lists eleven principles (L1–L11) and where we stand on each. The plan template and CLAUDE.md now ask for a learning check.
- **ADR 0005 amendment** (status *proposed*) records the change to (c).

## How to run / use it
- Lessons page: "How much help should Prof AI give?" on the form; a level dropdown on each chat row.
- API: `PATCH /api/students/{student_id}/chats/{conversation_id}` with `{"support": "step_by_step" | "balanced" | "stretch"}` (tutors who manage the student; audited as `chat_support_changed`).
- Messages: `POST .../messages` with `{"content": "...", "to_tutor": true}` sends a student's message to the tutor only.

## Contracts other code can rely on
- `Lesson.support: SupportLevel = "balanced"` (`chat/models.py`); `StudentChat.support` is `null` for chats without a lesson.
- `asks_ai(conversation, content, author="student", to_tutor=False)` (`chat/service.py`): no lesson → always; `@AI` → always; otherwise student and not `to_tutor`. `web/src/ChatThread.tsx` `asksAi(shared, author, content, toTutor)` mirrors it.
- `SUPPORT_PROMPTS` and `support_section` (`chat/prompts.py`); `ContextInput.support` and `base_text` (`chat/context.py`). The support text counts towards `Layer.BASE`; `check_budget` refuses to start if the base prompt plus the largest level is over the base cap.
- `ChatService.set_support(student_id, conversation_id, support)`.
- `sendMessage(id, content, handlers, options, toTutor)` and `changeStudentChatSupport(...)` in `web/src/api.ts`.

## Tests added
- `tests/lesson_behaviour/`: who triggers Prof AI; each level reaches the model before the lesson material; the no-answers floor and the lesson-scope rule are in the prompts; levels count towards and fit the base cap; the startup check; changing a level (audited, tutor-only, unknown levels rejected, not for chats without a lesson).
- `web/src/lessonBehaviour.test.ts`: `asksAi` mirrors the server; starters need no `@AI`; the PATCH and `to_tutor` request shapes.
- **Changed to the new contract:** these tests pinned "students need `@AI`", which this feature changes on purpose. Each still checks what it checked before, now using *to tutor only* or a tutor's message:
  - in `tests/shared_chat/test_shared_chat.py`: `test_a_message_to_the_tutor_only_is_saved_and_costs_nothing` (renamed from `..._without_at_ai_...`), `test_only_a_whole_word_at_ai_counts` (now checks a tutor's message), the kill-switch test and the rate-limit test.
  - `SharedHarness.student_says` gained `to_tutor`.
  - in web: `sharedChat.test.ts` (`asksAi` takes the author), and `webRefresh.test.ts` (starters no longer start with `@AI`).

## Known issues / TODOs
- `prof eval dilution` has to be re-run on the new base prompt before merging (about $1 worst case). Results go here.
- The lesson-scope rule is prompt-only; the guard pipeline's topic check is still the firm control (R2).
- *Step by step* asks for the material's worked example first, but lessons don't mark worked examples yet. That comes with worksheet-first lessons.

## For the other dev
- ADR 0005 has a **proposed** amendment changing (c): students no longer need `@AI` in lesson chats. Accept it, or say what to change.
- New feature plans need a **Learning check** section (`docs/product/learning-science.md`).
