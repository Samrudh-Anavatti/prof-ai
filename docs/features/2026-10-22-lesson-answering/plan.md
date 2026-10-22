# Plan: Lesson answering works from the Lessons page, and one Send with a "Send to" toggle

- **Owner:** punji
- **Branch:** `fix/lesson-answering`
- **Date:** 2026-10-22

## Goal
A tutor who sets up a lesson for themselves and opens it from the Lessons page gets no working editor, help buttons or *Submit my answer*: `TutorChatPage` never passes `own`, so they see a tutor's view of a student's chat while Prof AI tells them to press a button that isn't there. Fix that, and replace the composer's two buttons (*Send* and *Ask Prof AI*, or *Ask Prof AI* and *Send to tutor only*) with one *Send* and a "Send to" toggle.

## Approach
- `TutorChatPage`: `own = studentId === me.id`. When it's the tutor's own chat, pass `own` and the `check`/`checkWorking` endpoints (`/api/chat/conversations/{id}/check` and `/working` already take the signed-in user as the owner).
- `ChatThread`: `recipients(shared, solving, viewer)` lists who the composer can send to, with the default first: a student in their lesson gets Prof AI (default) or *My tutor*; a tutor in a student's chat gets *Student* (default) or Prof AI; a tutor's own lesson and test chats get Prof AI only, with no toggle. `outgoing(recipient, solving, content)` turns the choice into what the server already understands (`to_tutor`, or an `@AI` mention). The server doesn't change.

## Risks
- **Correctness:** the wrong recipient would send a student's private note to Prof AI, or the reverse. `outgoing` is tested against `asksAi`, which mirrors the server's `asks_ai`, for every choice.
- **Abuse / cost:** no change. Every model call still goes through `ChatService`; the toggle only sets fields that already exist.
- **Child safety / data:** no new data. *My tutor* still uses `to_tutor`, so the tutor sees it and Prof AI doesn't.

## Learning check
Keeps *Submit my answer* the only way to finish a question (retrieval with feedback, L-register). Defaulting students to Prof AI matches the lesson-behaviour decision; no principle worked against.

## Files / modules touched
- `web/src/TutorChatPage.tsx`, `web/src/ChatThread.tsx`, `web/src/styles.css`

## Contracts added or changed
- `recipients`, `outgoing`, `Recipient`, `RECIPIENT_LABELS` exported from `ChatThread.tsx`.

## Tests to add
- `web/src/lessonAnswering.test.ts`: the options and default for each viewer, and that each choice reaches Prof AI or not as the server decides.

## Open questions
- None.
