# Plan: Describe it instead

- **Owner:** punji
- **Branch:** `feat/describe-lesson`
- **Date:** 2026-10-22

## Goal
A tutor can set up a lesson by describing it in their own words (typed, or dictated with the device's keyboard) instead of filling in each field. Prof AI drafts the title, topics, notes and support level, and the tutor checks the form before saving. The current form stays as it is: *Describe it instead* is an extra button in the corner of the form.

## Approach
- **Checklist:** the describe panel shows what a good description covers:
  - who it's for (year group or level);
  - the topic;
  - what they've already covered;
  - what they find hard;
  - how much help they should get;
  - what Prof AI should focus on or avoid.
  
  The checklist ids are fixed in `lessons/describe.py` (`CHECKLIST`) and mirrored in `web/src/lessons.ts`.
- **Drafting** (`lessons/describe.py`): the description and a fixed prompt (`lessons/prompts/describe_lesson.md`) go to the model, which returns JSON: `{title, topics, notes, support, unanswered}`. The prompt fills only what the description says (no invented facts), puts the year group, prior work, struggles and focus into the notes, sets `support` only when the description says how much help to give, and lists the checklist items the description didn't answer. The description is wrapped as data. The parser tolerates fences and prose, clips over-long fields to the lesson rules' limits, and drops unknown support levels and checklist ids.
- **Through `ChatService.draft_lesson(tutor, description)`:** kill switch, global budget, rate limit, charged to the tutor, with 800 output tokens. The input is capped at 4,000 characters.
  - **Model:** a description is usually about a student, so it runs on the tutor's preferred model only if that model is approved for student conversations; otherwise it uses the default (Luna).
  - **Shared steps:** `extract_worksheet` and `draft_lesson` share one helper for the steps they have in common.
- **API:** `POST /api/lessons/describe` with `{description}` returns a `LessonDraft` (tutors only).
- **Lessons page:**
  - A *Describe it instead* button sits in the corner of the *New lesson chat* heading and opens a panel with the checklist and a text box.
  - *Draft the lesson* fills the title, topics, notes and support level. A field the draft left empty keeps whatever was there.
  - Checklist items the description didn't answer are marked in the panel.
  - Fields the draft couldn't fill are highlighted, with "Not in your description", until the tutor edits them.
  - Nothing is saved until *Set up chat*, which still goes through `validate_lesson`.

## Risks
- **R6 (wrong content in a lesson):** the draft only fills a form the tutor reviews. The prompt forbids inventing details. Over-long fields are clipped, and saving still goes through `validate_lesson`.
- **Data:** a description can name a student and their difficulties. It goes only to a model approved for student conversations, and it isn't stored. Only the notes the tutor saves are kept, as today.
- **R23 (prompt injection):** the description is the tutor's own text. It's wrapped and labelled as data anyway, and the drafted notes go into the lesson layer, which the base prompt already treats as information.
- **R3 (cost):** about 1k tokens in and at most 800 out, roughly $0.001 on Luna. It's rate-limited, inside the global budget, and charged to the tutor (tutors are exempt from the per-user cap, as for extraction).
- **Failure:** an unreadable reply gives a clear error ("fill the form in instead"). The kill switch stops drafting.

## Learning check
- It makes it quick to tell Prof AI what the student already knows and finds hard. That's what lets the support level and the notes fit the student (**L2 expertise reversal**), and it starts from prior knowledge rather than a blank slate.
- The checklist asks for the support level explicitly, so tutors choose it instead of leaving the default.
- Nothing works against a principle: the lesson's questions and worked examples are unchanged.

## Files / modules touched
- `src/prof_ai/lessons/describe.py` (new), `lessons/prompts/describe_lesson.md` (new), `lessons/api.py`, `chat/service.py`
- `web/src/api.ts`, `lessons.ts`, `LessonsPage.tsx`, `styles.css`
- Docs: INDEX, CLAUDE.md, README, learning science

## Contracts added or changed
- `LessonDraft(title, topics, notes, support | None, unanswered)`, `CHECKLIST`, `draft_request`, `parse_draft`, `DraftError` (`lessons/describe.py`)
- `ChatService.draft_lesson(tutor, description) -> LessonDraft`
- `POST /api/lessons/describe` `{description}` → `LessonDraft`
- Web: `draftLesson(description)`, `DESCRIBE_CHECKLIST`

## Tests to add
Under `tests/describe_lesson/`:
- The draft is parsed from JSON in fences or prose.
- Over-long fields are clipped; unknown support levels and checklist ids are dropped.
- The description is wrapped as data and capped.
- A tutor drafts a lesson and pays for it, with the output cap applied.
- Tutors only; the kill switch is respected.
- An unapproved preferred model falls back to the default, and an approved one is used.
- An unreadable reply gives a 502 with a clear message.

In `web/src/describeLesson.test.ts`:
- The request shape.
- Applying a draft fills the fields and keeps any the draft left empty.

## Open questions
- Should the tutor be able to dictate in the app? For now, the device's own dictation (the keyboard's mic) works in the text box.
