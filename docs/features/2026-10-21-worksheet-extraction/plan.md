# Plan: Worksheet extraction and tutor review

- **Owner:** punji
- **Branch:** `feat/worksheet-extraction`
- **Date:** 2026-10-21

## Goal
A tutor uploads a worksheet PDF and gets its worked examples and questions (with answers from the answer key) as an editable list, saved with the lesson. This is the first stage of worksheet-first lessons ([ADR 0006](../../decisions/0006-worksheet-first-lessons.md), proposed). The student's question-by-question page comes next.

## Approach
- **Data:** `Lesson.worked_examples: [WorkedExample(title, text)]` and `Lesson.questions: [Question(number, text, answer?)]`, both in `chat/models.py`.
- **Extraction** (`lessons/worksheet.py`): the selected pages' text and a fixed prompt (`lessons/prompts/extract_worksheet.md`) go to the model, which returns JSON parsed into a `Worksheet`. The prompt keeps the document's numbering, takes answers only from its answer key (never works them out), writes maths in LaTeX, and treats the document as data, not instructions.
- **Through `ChatService.extract_worksheet(tutor, text)`:** kill switch, global budget, rate limit, the tutor's preferred model (unapproved models allowed: tutor content), and the cost charged to the tutor. Input is capped at the lesson layer's 12k tokens; output at 6k.
- **API:** `POST /api/lessons/worksheet` with `{text}` → `{title, topics, worked_examples, questions}` (tutors only).
- **Lesson layer:** `render_lesson` adds the worked examples and the questions **without answers**. `web/src/lessons.ts` mirrors it for the token meter. `validate_lesson` tidies them, and needs the licence tick for them as it does for material.
- **Lessons page:** after picking PDF pages, *Extract questions and examples* fills an editable review list: worked examples (title, text) and questions (number, text, answer), with remove and add buttons. It also fills the title and topics if they're empty.
- **Students see nothing new yet:** `LessonOverview` is unchanged, and answers never leave the server for a student.
- **Repo safety:** `dummy-data/` (real sample worksheets) is gitignored.

## Learning check
- **L1 Worked examples** and **L3 retrieval practice:** lessons now carry the tutor's worked examples and questions as structure, not just text.
- Prof AI sees the questions, so its help can be about the actual question (L7 step-based hints).

## Risks
- **R4 (answers handed over):** answers are never in the lesson layer or a student's response; tested. A worked example that solves the same problem as a question is visible to the tutor at review.
- **R6 / R7 (wrong extraction):** the tutor reviews and edits everything before saving. The prompt forbids inventing answers, so a missing key leaves the answer blank.
- **R23 (prompt injection in the document):** the document is wrapped and labelled as data. Questions and examples then go into the lesson layer, which the base prompt already treats as information. Only tutors upload.
- **R12 (licence):** saving questions or worked examples needs the licence tick, as material does.
- **R3 (cost):** about $0.002 per worksheet on Luna. Capped input and output, rate-limited, inside the global budget.
- **Data:** worksheet text may go to an unapproved model (for example Ollama) if that's the tutor's preferred model. It's tutor content, not student data. Tutors shouldn't put student names in uploads.
- **Failure:** a bad model reply gives a clear error ("add them by hand"); nothing is saved until the tutor saves.

## Files / modules touched
- `src/prof_ai/chat/models.py`, `chat/service.py`, `lessons/worksheet.py` (new), `lessons/prompts/extract_worksheet.md` (new), `lessons/rules.py`, `lessons/api.py`
- `web/src/api.ts`, `lessons.ts`, `LessonsPage.tsx`, `styles.css`
- `.gitignore`; docs: ADR 0006, CLAUDE.md, README, INDEX, risks, learning science

## Contracts added or changed
- `WorkedExample`, `Question`, `Lesson.worked_examples`, `Lesson.questions`
- `Worksheet`, `extraction_request`, `parse_worksheet`, `WorksheetError`
- `ChatService.extract_worksheet(tutor, text) -> Worksheet`
- `POST /api/lessons/worksheet`
- `render_lesson` (and `renderLesson` in web) include examples and questions, never answers

## Tests to add
`tests/worksheet_extraction/`:
- parsing (fences, bad JSON, empty questions dropped)
- the request (text wrapped, the size cap)
- the API: tutor-only, budget and kill switch, cost charged, the preferred model used
- the lesson layer includes questions and examples but never answers
- the student's view never includes answers
- the licence is needed for questions

Web: `renderLesson` mirrors the server, and the request shape.

## Open questions
- None for this stage. Scans (vision or Document Intelligence) are a later choice; see ADR 0006.
