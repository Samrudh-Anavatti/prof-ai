# Plan: Lesson behaviour: support levels, staying on the lesson, Prof AI by default

- **Owner:** punji
- **Branch:** `feat/lesson-behaviour`
- **Date:** 2026-10-21

## Goal
Make lesson chats teach the way a tutor would set them up:

1. **Support levels.** A tutor picks how much help a student gets in each lesson: *Step by step*, *Balanced* or *Stretch*. A confident student shouldn't be walked through one tiny step at a time; a beginner should. No level ever hands over final answers.
2. **Stay on the lesson.** In a lesson chat, Prof AI keeps to the lesson (and the background the student needs for it), and points other questions to the tutor. Students have no general chat, and we're not adding one.
3. **Prof AI by default.** In a lesson chat, a student's message goes to Prof AI unless they choose *Send to tutor only*. Tutors still ask Prof AI with `@AI`. This amends ADR 0005 (c), where every message needed `@AI`: a student working alone during the week shouldn't have to type it.
4. **Clearer wording.** "however the student asks" becomes "no matter how the student asks".
5. **Learning science.** Add `docs/product/learning-science.md`, a short list of research-backed learning principles and how far the product follows each, and a learning check in the feature plan template.

## Approach
- `Lesson.support: "step_by_step" | "balanced" | "stretch"`, default `balanced`. Each level maps to a fixed prompt in `chat/prompts/support/<level>.md` (repo-owned, never tutor-written). `compose_system_prompt` adds it as its own section after the teaching style and before the lesson material, so it isn't mistaken for material. Its size counts towards the base layer, since it's our own fixed text; `check_budget` checks the base prompt plus the largest level fits the base cap.
- The pace rules move out of the base prompt ("one hint or one step at a time", "one idea per message") into the levels. The base prompt keeps the floor: coach, don't hand over answers, confirm answers they've worked out.
- Tutors change a lesson's level on the Lessons page at any time: `PATCH /api/students/{id}/chats/{chat_id}` with `{"support": ...}`, written with `update_conversation` and audited.
- `asks_ai(conversation, content, author, to_tutor)`: chats without a lesson always ask; any `@AI` asks; otherwise a student's message asks unless `to_tutor`, and a tutor's doesn't. `NewMessage` gains `to_tutor: bool = False`.
- Base prompt boundary: in a lesson chat, stay on the lesson and its background knowledge; say other questions are for the tutor and steer back. The reminder says the same.
- Web: a support-level picker on the new-lesson form and on each chat row; in a student's lesson chat, *Send* asks Prof AI and *Send to tutor only* doesn't; starter prompts no longer add `@AI` for students.
- Eval: scenarios carry a support level (default `balanced`, as in the app); add a *Stretch* answer-demand case and an off-lesson redirect case.

## Learning check
- **L2 Expertise reversal:** support levels fit the help to the student, rather than the same step-by-step pace for everyone.
- **L1 Worked examples:** *Step by step* walks through a worked example from the material first.
- **L5 Productive struggle, L6 self-explanation:** *Balanced* and *Stretch* let the student try before helping, and *Stretch* asks them to explain their reasoning.

## Risks
- **R4 (handing over answers):** a looser level could drift into giving answers. Controls: every level keeps the "never give final answers" floor, which stays in the base prompt and the reminder; new eval case `stretch-answer-demand`; levels are fixed text in the repo, not free text.
- **R2 (off-topic):** the stricter lesson scope is prompt-only. The firm control is still the guard pipeline's topic check (planned).
- **R3 (cost):** Prof AI by default means more model calls from students who used to write without `@AI`. Every call still goes through `ChatService`'s budgets, rate limit and kill switch; `to_tutor` messages cost nothing.
- **R24 (adult–child messaging):** unchanged. *Send to tutor only* messages are stored and visible exactly like before.
- **R20 (prompt weakening):** the level is an enum the server maps to repo text, so a tutor can't inject instructions through it. Changes are audited.
- **R22 (dilution):** the base prompt changes, so `prof eval dilution` is re-run.

## Files / modules touched
- `src/prof_ai/chat/`: `models.py`, `prompts.py`, `prompts/tutor.md`, `prompts/reminder.md`, `prompts/support/*.md`, `context.py`, `service.py`, `api.py`
- `src/prof_ai/lessons/api.py`, `src/prof_ai/evals/dilution.py`, `src/prof_ai/evals/scenarios.json`
- `web/src/`: `api.ts`, `ChatThread.tsx`, `ChatPage.tsx`, `LessonsPage.tsx`
- Docs: ADR 0005 amendment, `docs/product/learning-science.md`, the plan template, CLAUDE.md, README, INDEX

## Contracts added or changed
- `Lesson.support` (default `balanced`); `StudentChat.support`.
- `POST .../messages` body: `{content, to_tutor?}`.
- `asks_ai(conversation, content, author="student", to_tutor=False)`: **behaviour change** for students in lesson chats.
- `PATCH /api/students/{student_id}/chats/{conversation_id}` with `{support}`: tutors only, audited as `chat_support_changed`.
- `compose_system_prompt(..., support=None)` and `ContextInput.support`.

## Tests to add
`tests/lesson_behaviour/`: who triggers Prof AI (student by default, `to_tutor`, tutor with and without `@AI`); each level's prompt reaches the model, in the right place; levels keep the no-answers floor; the base layer fits with the largest level; `PATCH` changes the level, is tutor-only, audited, and rejects unknown levels; `to_tutor` messages don't call the model or cost anything. Web: `asksAi` mirrors the server; starter prompts in lesson chats need no `@AI`.

Tests in `tests/shared_chat/` and `web/src/` that pinned "students need `@AI`" are updated to the new contract (the behaviour they checked was deliberately changed), keeping what else they check.

## Open questions
- None. Decided with Punji on 2026-10-21.
