# Feature index

Read this first each session. One row per feature, newest at the bottom. Agents add a row when writing `plan.md` and update it on merge.

| Date | Feature | Owner | Status | Docs |
|------|---------|-------|--------|------|
| 2026-10-07 | Repo setup | Sam | merged | [handover](2026-10-07-repo-setup/handover.md) |
| 2026-10-13 | Repurpose repo for Prof AI | Sam | merged | [plan](2026-10-13-repurpose-prof-ai/plan.md) · [handover](2026-10-13-repurpose-prof-ai/handover.md) |
| 2026-10-14 | Product vision, architecture and risk docs | Sam | merged | [plan](2026-10-14-product-vision/plan.md) · [handover](2026-10-14-product-vision/handover.md) |
| 2026-10-14 | App skeleton and Azure infrastructure | Sam | merged | [plan](2026-10-14-app-skeleton-infra/plan.md) · [handover](2026-10-14-app-skeleton-infra/handover.md) |
| 2026-10-14 | Content store basics | Sam | merged | [plan](2026-10-14-content-store/plan.md) · [handover](2026-10-14-content-store/handover.md) |
| 2026-10-14 | Auth: invite-only sign-in, users, locks | Sam | merged | [plan](2026-10-14-auth/plan.md) · [handover](2026-10-14-auth/handover.md) |
| 2026-10-18 | Frontend skeleton: React SPA served by FastAPI (ADR 0003) | Sam | merged | [plan](2026-10-18-frontend-skeleton/plan.md) · [handover](2026-10-18-frontend-skeleton/handover.md) |
| 2026-10-18 | Tutor chat PoC with per-user AI profiles | Sam | merged | [plan](2026-10-18-tutor-chat/plan.md) · [handover](2026-10-18-tutor-chat/handover.md) |
| 2026-10-18 | Teaching style editor in the web UI, plus README overhaul | Sam | merged | [plan](2026-10-18-teaching-style-editor/plan.md) · [handover](2026-10-18-teaching-style-editor/handover.md) |
| 2026-10-18 | Users admin page with email-code invites (ADR 0004) | Sam | merged | [plan](2026-10-18-user-admin/plan.md) · [handover](2026-10-18-user-admin/handover.md) |
| 2026-10-19 | Context budget, conversation memory and money-based budgets (ADR 0005, feature a) | Sam | merged | [plan](2026-10-19-context-budget/plan.md) · [handover](2026-10-19-context-budget/handover.md) |
| 2026-10-19 | Lessons and tutor-created chats: lesson setup, uploads within the lesson cap (12k now), at most 5 chats per student (ADR 0005, feature b) | Sam | merged | [plan](2026-10-19-lessons/plan.md) · [handover](2026-10-19-lessons/handover.md) |
| 2026-10-20 | Shared tutor–student chat with `@AI` (ADR 0005, feature c) | Sam | merged | [plan](2026-10-20-shared-chat/plan.md) · [handover](2026-10-20-shared-chat/handover.md) |
| 2026-10-20 | Web app visual refresh: Lexend, friendlier chat, cards, focus and motion | Sam | merged | [plan](2026-10-20-web-refresh/plan.md) · [handover](2026-10-20-web-refresh/handover.md) |
| 2026-10-21 | Model providers: one adapter for OpenAI-compatible providers, Ollama Cloud models for tutors' own chats, `approved_for_student_conversations` enforced by `ChatService`, a model picker per lesson (ADR 0005 amendment, proposed) | Punji | merged | [plan](2026-10-21-model-providers/plan.md) · [handover](2026-10-21-model-providers/handover.md) |
| 2026-10-21 | Maths rendering: Markdown and typeset maths (KaTeX to MathML) in Prof AI's replies | Punji | merged | [plan](2026-10-21-maths-rendering/plan.md) · [handover](2026-10-21-maths-rendering/handover.md) |
| 2026-10-19 | Context dilution eval: safety and coaching hold at lessons up to 40k; caps cut to fit 50k tokens a minute; safer filtered message | Sam | merged | [plan](2026-10-19-context-dilution-eval/plan.md) · [handover](2026-10-19-context-dilution-eval/handover.md) |
| — | Knowledge graph (chapter extraction, curricula) filling the reference layer (4k now) | Sam | planned | — |
| — | Guard pipeline (Prompt Shields, topic checks, safeguarding flags, auto-lock): required before real students | Sam | planned | — |
| — | End-of-sprint lint/cleanup pass | both | planned | — |
| 2026-10-21 | Lesson behaviour: support levels per lesson, staying on the lesson, Prof AI answers students by default (ADR 0005 amendment, proposed), learning-science register | Punji | merged | [plan](2026-10-21-lesson-behaviour/plan.md) · [handover](2026-10-21-lesson-behaviour/handover.md) |
| 2026-10-21 | Worksheet extraction: draft questions (with answer-key answers, tutor-only) and worked examples from a worksheet PDF, reviewed on the Lessons page ([ADR 0006](../decisions/0006-worksheet-first-lessons.md), proposed) | Punji | merged | [plan](2026-10-21-worksheet-extraction/plan.md) · [handover](2026-10-21-worksheet-extraction/handover.md) |
| 2026-10-22 | Student lesson page: worked examples first by support level, one question at a time with help buttons, "Check my answer" (exact match, then a model check that never gives the answer), messages tagged by question, per-question progress for student and tutor (ADR 0006) | Punji | merged | [plan](2026-10-22-student-lesson-page/plan.md) · [handover](2026-10-22-student-lesson-page/handover.md) |
| 2026-10-22 | Describe it instead: draft a lesson's title, topics, notes and support level from one description, with a checklist of what to cover, next to the existing form | Punji | merged | [plan](2026-10-22-describe-lesson/plan.md) · [handover](2026-10-22-describe-lesson/handover.md) |
| — | Later: scanned worksheets: page images to a vision model, or Azure Document Intelligence (ADR 0006) | — | planned | — |
| — | Later: reuse lessons across students: a tutor's lesson library, so similar lessons aren't rebuilt (and re-extracted) per student | — | planned | — |
| 2026-10-22 | Show your working: students write their working step by step with a live maths preview, check it as they go, and submit for a verdict (correct, show your working, slip, not yet); Prof AI works out missing answers for the tutor to confirm (ADR 0006) | Punji | merged | [plan](2026-10-22-show-your-working/plan.md) · [handover](2026-10-22-show-your-working/handover.md) |
| — | **Bug:** in lesson chats, Prof AI tells the student an answer is "exactly right" and moves on to the next question, but the question isn't marked done (progress still shows 0 tries). Only *Submit my answer* completes a question. Likely fix: add to `chat.checking.question_reference` (and the base prompt's lesson rules) that Prof AI may confirm steps but never declares a question finished or moves on; it tells the student to submit their working instead. Add an eval case | — | planned | — |
| — | **Bug:** switching questions on the lesson page doesn't change the chat: the thread shows every question's messages together, so question 3 opens under question 1's conversation. Options: filter the thread to messages tagged with the current question (with a "show all" toggle), or scroll to and highlight that question's latest message. Untagged messages need a home either way | — | planned | — |
| — | **Bug:** a tutor trying a lesson in their own chat ("Yourself, to try a lesson out") gets the tutor view: no working editor, help buttons or *Submit my answer*, and every message needs `@AI`. The owner of a chat should get the student controls; `ChatThread`'s `viewer` and `chat.service.asks_ai` decide this | — | planned | — |
| — | Later: adaptive practice: an Anki-style scheduler that gives a student more or fewer questions of each type based on how confident they seem (right first time, help needed, slips), bringing weak types back over the following days (learning science L9, L10) | — | planned | — |
| — | Later: help-seeking signals: show the tutor when a student guesses rapidly or keeps asking for answers (learning science L11); a signal, never a lock | — | planned | — |

Status values: `planned`, `in-progress`, `merged`, `abandoned`.
