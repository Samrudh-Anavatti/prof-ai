# Handover: Worksheet extraction and tutor review

- **Owner:** punji
- **PR:** see the PR for `feat/worksheet-extraction`
- **Merged:** pending

## What was built
As planned:
- **`Lesson.worked_examples` and `Lesson.questions`** (`chat/models.py`). Each question has a `number`, `text` and an optional tutor-only `answer`.
- **Extraction** (`lessons/worksheet.py` and `lessons/prompts/extract_worksheet.md`): worksheet text in, `{title, topics, worked_examples, questions}` JSON out. The prompt keeps the document's numbering, takes answers only from the answer key (never works them out), writes maths in LaTeX with £ for money, lists worked-example steps one per line, and treats the document as data.
- **`ChatService.extract_worksheet(tutor, text)`:** kill switch, global budget, rate limit, the tutor's preferred model (which may be unapproved for students), and the cost charged to the tutor. Input is capped at 12k tokens, output at 6k. A reply that can't be parsed returns 502 with "add them by hand".
- **`POST /api/lessons/worksheet`** (tutors only).
- **Lesson layer:** `render_lesson` adds the worked examples and the questions, without answers. `web/src/lessons.ts` mirrors it for the token meter. `validate_lesson` tidies questions (blank ones dropped, a blank answer becomes `null`) and asks for the licence tick when a lesson has questions or examples.
- **Lessons page:** after picking pages, *Extract questions and examples* (alongside *Add pages as text*) fills an editable review list: worked examples (title, text) and questions (number, text, answer), each removable, plus *Add a question*. It fills the title and topics if they're empty, and records the PDF as a source.
- **`dummy-data/`** is gitignored, so the sample worksheets can't be committed.

**Tested on the two sample PDFs** with Luna:
- **The worksheet** (3 pages): 15 questions with correct numbering (A1.1–B2.7) and all answers from the key. 14 s, $0.0015.
- **The worked-examples PDF** (5 pages): all 5 worked examples with their steps, and 4 practice questions with no answers, because it has no key. 9 s, $0.002.
- **One finding:** the worksheet's answer key covers a Part C (C1–C3), but the PDF has no Part C questions. Its text layer and images contain none, so there was nothing to extract.

## How to run / use it
Lessons page → pick a student → choose a PDF → tick the pages → *Extract questions and examples* → check the list → tick the licence box → *Set up chat*.

## Contracts other code can rely on
- `WorkedExample`, `Question`, `Lesson.worked_examples`, `Lesson.questions` (`chat/models.py`).
- `Worksheet`, `extraction_request`, `parse_worksheet`, `WorksheetError`, `EXTRACT_OUTPUT_TOKENS`, `MAX_WORKSHEET_TOKENS` (`lessons/worksheet.py`).
- `ChatService.extract_worksheet(tutor, text) -> Worksheet`.
- **Answers are never in `render_lesson`'s output or a student's response.** The student page (next stage) must keep it that way. It should attach only the current question's answer to a single turn, and run "check my answer" as its own call.
- `extractWorksheet(text)`; `Lesson.worked_examples` and `Lesson.questions` in `web/src/api.ts`.

## Tests added
- `tests/worksheet_extraction/`:
  - Parsing (fences, prose, unreadable replies).
  - The request (document wrapped as data, the size cap).
  - The API: tutor-only, kill switch, cost charged to the tutor, output cap, oversized text, unreadable replies.
  - The tutor's preferred (unapproved) model is used.
  - Questions and examples reach the model but answers never do; a student never receives answers.
  - The licence is required and questions are tidied.
- `web/src/worksheetExtraction.test.ts`: `renderLesson` mirrors the server without answers, tidying matches, and the request shape.

## Known issues / TODOs
- **Not tried in a browser end to end:** that would create a real lesson in the shared Cosmos database. Try it on the live app after merging.
- **Scanned pages** (no text) can't be extracted yet. See ADR 0006 for the vision and Document Intelligence options.
- Tutors can't edit a saved lesson's questions yet; delete and recreate for now.
- A worked example that solves the same problem as a question gives that answer away (in the samples, the worked examples solve A1.1–A1.3 and A2.6). The tutor sees both at review and decides.
- Students see nothing new until the student lesson page lands.
- The extraction prompt hasn't been through an eval.

## For the other dev
- [ADR 0006](../../decisions/0006-worksheet-first-lessons.md) is **proposed**: lessons become worksheet-first. Accept it, or say what to change.
- Never send `Question.answer` to a student's browser or put it in the lesson layer (CLAUDE.md).
