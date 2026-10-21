# Handover: Describe it instead

- **Owner:** punji
- **PR:** see the PR for `feat/describe-lesson`
- **Merged:** pending

## What was built
As planned:
- **Describe it instead** (Lessons page): a button in the corner of *New lesson chat* opens a panel with the checklist and a text box. You can type the description, or dictate it with the device's keyboard.
  - The checklist asks: who it's for, the topic, what they've covered, what they find hard, how much help to give, and what to focus on or avoid.
- **Draft the lesson** fills the title, topics, notes and support level:
  - A field the draft left empty keeps what was already there.
  - Checklist items the description didn't answer are marked "Not in your description".
  - Form fields the draft couldn't fill are highlighted until edited. That covers the support level whenever the description didn't say.
  - *Draft it again* redrafts after you add to the description.
- **Nothing is saved until *Set up chat***, which still goes through `validate_lesson`. The description itself is never stored.
- **Server:** `POST /api/lessons/describe` with `{description}` returns `{title, topics, notes, support, unanswered}`. It goes through `ChatService.draft_lesson`:
  - kill switch, global budget and rate limit;
  - 800 output tokens, charged to the tutor;
  - descriptions over 4,000 characters are refused.
  
  The reply is clipped to the lesson rules' limits. Unknown support levels and checklist ids are dropped.
- **Model:** a description is usually about a student, so it runs on the tutor's preferred model only if that model is approved for student conversations; otherwise it uses the default (Luna). Worksheet extraction is unchanged and may still use any model.
- **Refactor:** `extract_worksheet` and `draft_lesson` share `ChatService._tutor_task` (kill switch, budgets, limiter, call, charge). Extraction behaves the same. The one change is that a content-filter hit now says "blocked that text" instead of "blocked that material".

## How to run / use it
Lessons page → *New lesson chat* → *Describe it instead*. Write a few sentences that cover the checklist, press *Draft the lesson*, check the highlighted fields, then *Set up chat* as usual. Each draft costs about $0.001 on Luna.

## Contracts other code can rely on
- `prof_ai.lessons.describe`: `LessonDraft`, `CHECKLIST`, `draft_request`, `parse_draft`, `DraftError`, `MAX_DESCRIPTION_CHARS`, `DRAFT_OUTPUT_TOKENS`.
- `ChatService.draft_lesson(tutor, description) -> LessonDraft`.
- `POST /api/lessons/describe` (tutors only).
- Web:
  - `draftLesson`, `LessonDraft` (`api.ts`)
  - `DESCRIBE_CHECKLIST`, `applyDraft`, `LessonFields`, `DraftField` (`lessons.ts`)
  - `DescribeLesson.tsx`

  `DESCRIBE_CHECKLIST`'s ids must match `CHECKLIST` in Python. Both are pinned by tests.

## Tests added
- `tests/describe_lesson/`:
  - parsing from fences or prose;
  - clipping and dropping unknown values;
  - the description wrapped as data and capped;
  - a tutor drafts and pays, with the output cap;
  - tutors only;
  - the kill switch;
  - bad input and unreadable replies;
  - an unapproved preferred model falls back to the default, and an approved one is used.
- `web/src/describeLesson.test.ts`:
  - the request shape;
  - `applyDraft` fills the fields, keeps typed ones and flags what's missing;
  - the panel marks unanswered checklist items;
  - the checklist ids.

## Known issues / TODOs
- **Not exercised against a real model:** the prompt hasn't been tried live yet. Try a couple of descriptions after merging, including one that leaves things out.
- **Highlights:** they clear when you edit a field, not when you close the panel.
- **No dictation button in the app:** the device keyboard's mic works in the text box.

## For the other dev
- `_tutor_task` is now the place for any tutor-only setup call that isn't part of a chat (for example knowledge-graph drafting). It keeps such calls inside the kill switch, the budgets and the rate limit.
