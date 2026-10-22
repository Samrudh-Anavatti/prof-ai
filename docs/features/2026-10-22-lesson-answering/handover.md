# Handover: Lesson answering works from the Lessons page, and one Send with a "Send to" toggle

- **Owner:** punji
- **PR:** see the PR for `fix/lesson-answering`
- **Merged:** 2026-10-22

## What was built
As planned.
- **A lesson you set up for yourself works from the Lessons page.** `TutorChatPage` now passes `own` when the chat's student is the viewer, plus the check endpoints, so you get the working editor, help buttons and *Submit my answer* there too. Before, only the Chat page did, so #28's fix for bug 3 looked broken when the lesson was opened from Lessons.
- **One Send button with a "Send to" toggle.**
  - Students in a lesson: **Prof AI** (default) or **My tutor**.
  - Tutors in a student's chat: **Student** (default) or **Prof AI**, which adds `@AI`.
  - A tutor's own lesson and test chats: Prof AI only, with no toggle.

  The choice sticks while the chat is open. The placeholder says who will get the message. Typing `@AI` still works.

## How to run / use it
- On the Lessons page, set up a lesson for yourself and open it: work a question and press *Submit my answer*.
- As a student, flip the toggle to *My tutor* and send: Prof AI doesn't reply.

## Contracts other code can rely on
- `recipients(shared, solving, viewer)`: who the composer can send to, the default first.
- `outgoing(recipient, solving, content)`: `{content, toTutor}` to send. It adds `@AI` only for Prof AI when the viewer isn't the one working the questions.
- The server is unchanged.

## Tests added
- `web/src/lessonAnswering.test.ts`: the options and defaults for each viewer, and that each choice reaches Prof AI or not, checked through `asksAi`.
- No existing test changed.

## Known issues / TODOs
- **Not tried on the live app or against Luna.** I checked it against a local harness: `ChatThread` with fake endpoints and the real stylesheet, at desktop and phone widths, in light and dark. Submitting, the help routing and both toggle choices worked there.
- The lesson panel is still capped at 60% of the chat column and scrolls, so on a phone the working editor takes some scrolling.

## For the other dev
- Sam: the composer no longer has *Ask Prof AI* or *Send to tutor only* buttons. New composer options should go through `recipients` and `outgoing`.
