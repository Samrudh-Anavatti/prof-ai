# 0006: Worksheet-first lessons

- **Status:** accepted (proposed 2026-10-21 by Punji, accepted by Sam 2026-10-21, including the show-your-working amendment). Built in stages: extraction and tutor review ([worksheet extraction](../features/2026-10-21-worksheet-extraction/plan.md)), then the student's lesson page.

## Context
A lesson today is a title, topics, notes and a block of PDF text in the prompt, with a chat on top. A student who is stuck doesn't know what to ask a blank chat box, and the app has no idea which questions the student is meant to answer. The vision's weekly loop was always questions first (Practise → Mark → Re-explain); chat came first only because it was built first.

The research we follow points the same way (see [learning science](../product/learning-science.md)):
- **L1 worked examples:** beginners learn more from studying a worked example and then practising.
- **L3 retrieval practice:** answering questions builds memory.
- **L2 expertise reversal:** confident students should skip ahead.

## Decision
- **A lesson is worked examples plus questions,** with Prof AI as help on each question, not a chat with material attached.
- **Questions come from the tutor's worksheet, not from the model.** A model call reads the worksheet and returns the title, topics, worked examples, and questions with their answers from the answer key. The tutor reviews and edits everything before saving. Generating new questions stays in Phase 2 (R15).
- **Answers are tutor-only.** They're stored with the lesson, never put in the lesson layer, and never sent to a student's browser. They're used only to check a student's answer, and to keep Prof AI's hints right for the question the student is on, attached to that one turn and never kept in the history.
- **Extraction reads text first.** The PDF's text goes to the tutor's preferred model, or the default. Worksheets are tutor content, not student data, so models not approved for student conversations may do this. Cost: about $0.002 per worksheet on Luna. Each worksheet is capped at the lesson layer's 12k tokens.
- **Scans are later.** Image-only pages need page images and a vision model (GLM-5.3 Flash and DeepSeek V4.1 Flash accept images), or Azure Document Intelligence (about $1.50 per 1,000 pages, 500 free pages a month, text only, a new Azure resource). The choice is made when scans come up. Photos from students are Phase 2 with their own risk review (R14).
- **The student's page** (next stage) leads with the worked example at the *Step by step* level and goes straight to the questions at *Stretch*. It shows one question at a time with help buttons and "Check my answer", and tags chat messages by question so the tutor can see progress per question.

## Alternatives considered
- **Keep chat-first and improve the prompt.** Cheaper, but it doesn't fix the blank-box problem or give the tutor per-question progress.
- **Let the model generate questions.** Risk of wrong or off-curriculum questions (R15), and tutors trust their own worksheets. Later, with tutor approval.
- **Vision for every page.** It handles scans, but costs more and is slower for text PDFs, which the samples were.

## Consequences
- `Lesson` gains `worked_examples` and `questions` (each with an optional tutor-only `answer`), counted in the lesson cap.
- The model sees the questions (without answers) and the worked examples in the lesson layer.
- A worked example that solves the same problem as a question gives that answer away. The tutor sees both on the review screen and decides.
- Reusing a lesson across students (a tutor's lesson library) is planned for later and would save repeat extractions.

## Amendment 2026-10-22: show your working (Punji, accepted)
- **A question is done on the working, not the answer.** Students write their working step by step and submit it with a final answer. The model marks both against the key: `correct`, `show_working` (right answer, working missing), `slip` or `not_yet`. Only `correct` completes a question. Typing the right answer alone is no longer enough, and nothing is marked without a model call. An exact match can't be marked wrong, only sent back for working.
- **Students can check unfinished working** at any point, to get a hint at the step they're on, without being marked.
- **Missing answer keys:** the tutor can ask Prof AI to work them out. They must confirm each one before the lesson saves. A question still saved without a key is marked by the model alone, labelled unverified for the tutor.
- **Every attempt keeps its working,** so the tutor reviews how the student got there ([show your working](../features/2026-10-22-show-your-working/plan.md)).
