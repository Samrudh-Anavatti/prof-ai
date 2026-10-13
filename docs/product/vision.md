# Vision

Living draft. Challenge anything here. Update it when the idea moves.

## The idea

An AI-assisted tutoring platform built around a human tutor, not one that replaces them. The tutor teaches a live one-hour lesson on a topic, usually a textbook chapter from a curriculum. During the week, each student keeps working on the platform. They do the questions the tutor assigned, and their own AI study assistant re-explains the chapter, grounded only in the content the tutor uploaded. The tutor sees everything: answers, marks, chat transcripts and usage.

**Students:** grades 6–12.
**First users:** Sam and Punjy as head tutors, each with 5–6 students.

## The weekly loop (first cut)

1. **Teach.** The tutor runs a live lesson on a chapter.
2. **Assign.** The tutor assigns that chapter plus a question set to each student.
3. **Practise.** The student logs in and sees the chapter and the questions, then submits answers. Answers are typed for now.
4. **Mark.** Software marks what it can deterministically. AI marks the rest against a rubric. Low-confidence marks go to the tutor.
5. **Re-explain.** The student chats with their assistant. It stays scoped to the assigned material, nudges rather than handing over answers, and is heavily guarded.
6. **Review.** The tutor sees per-student results, what they got wrong, chat transcripts, flags and usage, all ahead of the next lesson.

## Principles

- **Risk-first.** Every feature starts with "how could this be abused, leak, cost money or hurt a child?" See [risks.md](risks.md).
- **The tutor stays in the loop.** The AI drafts and the tutor decides. AI marks are provisional, and any tutor can override them.
- **Ground everything in tutor content.** The assistant explains from our material, not the open internet.
- **Be cheap by design.** Small models by default, hard budgets per student, no always-on search clusters. See [architecture.md](architecture.md).
- **Build for us first.** Tutor tooling can be scripts or a CLI while the users are two competent engineers. Self-service UI comes later.

## Roadmap (rough, will change)

| Phase | Scope |
|-------|-------|
| 0 | Repo, docs, Azure group, stack ADR (done/now) |
| 1 (MVP) | Student login; assignment view (chapter + questions); typed submissions; deterministic and AI marking with tutor override; grounded chat with guardrails, locks and budgets; tutor review (results, transcripts, usage report). Tutor admin via scripts/CLI |
| 2 | Photo/scan upload of handwritten working with AI analysis; question generation targeted at mistakes; pulling diagrams from supplementary books |
| 3 | Whiteboard input; self-service tutor UI; more tutors per account; parent view; multi-language |

Each phase-2+ item gets its own risk review before it's planned. For example, image upload brings inappropriate-image and PII-in-photo risks that typed answers don't have.

## Business perspective

**Problem.** Between lessons, students get stuck and lose momentum, and the tutor has no visibility until the next session. Generic AI chatbots give answers away, wander off-topic and aren't aligned to what was taught.

**Positioning.** "Your tutor, between lessons." Generic AI tutors are general-purpose. This one differs because:
- the tutor relationship stays central
- answers are grounded in the tutor's own curriculum-aligned content
- the tutor gets full visibility of what each student did

**Who pays, in stages:**
1. **Our own students.** The platform is bundled into the tutoring fee. This validates the value: do students use it, and do results improve?
2. **Independent tutors and small tutoring centres** (B2B SaaS, per student per month). This needs the self-service UI, multi-tenancy and content isolation.
3. **Larger centres or schools.** This is a much higher compliance bar. Don't plan for it yet.

**Unit economics to validate in Phase 1:**
- **Cost per active student per month:** model tokens, safety calls and storage, plus a share of fixed hosting. The target is small enough to be absorbed into a tutoring fee. Hard per-student token budgets keep the worst case bounded.
- **Tutor time saved per week:** marking and spotting misconceptions.
- **Student engagement:** sessions per week, questions attempted, how often locks or flags happen.
- **Outcome signal:** marks on repeated topics over time.

**Business risks:**
- **Textbook copyright.** Using commercial textbooks in an AI system, and showing excerpts to students, may break licence terms. This matters more once we sell to other tutors. Prefer our own worksheets and notes, and check licences before uploading a book.
- **Children's data and safeguarding.** We'd be processing minors' data. Which regulations apply depends on where the students live (e.g. the UK ICO Children's Code / UK GDPR, or the local equivalent). This needs parental consent and a privacy notice before any real student uses the platform.
- **AI errors damage trust.** One confidently wrong explanation or unfair mark seen by a parent is costly. That's why marks are provisional and answers are grounded.
- **Platform cost drift.** Model prices and usage can change, so budgets and alerts are a hard requirement.

## Open questions

- **Jurisdiction:** where are the students, and which privacy and safeguarding rules apply?
- **Curricula and subjects:** which ones first? Maths is the easiest to mark deterministically.
- **Content rights:** which textbooks are we licensed to use this way?
- **Parents:** do they get any visibility in Phase 1?
- **Device:** what do students use, phone or laptop? This drives the UI and answer input.
- **Locks:** who can unlock a student, and is unlocking always manual?
