# Learning science

Living list. These are well-established findings from learning research that we build on, and how far Prof AI follows each one. It's a working guide, not a literature review: the source line is there so anyone can look a finding up.

Every feature plan has a **Learning check** that names the principles it applies or works against (see the plan template). If a feature works against one, say why. Update the table when a feature lands.

## Principles

| ID | Principle | What it says | Source | What it means for us |
|----|-----------|--------------|--------|----------------------|
| L1 | **Worked examples** | Beginners learn more from studying a worked example and then practising than from solving problems cold. | Sweller & Cooper, 1985 | Lessons lead with a worked example from the tutor's material before the questions, for students who need it. |
| L2 | **Expertise reversal** | What helps a beginner (worked examples, small steps) stops helping, and can get in the way, once a student is competent. | Kalyuga et al., 2003 | Fit the help to the student: support levels per lesson, not one pace for everyone. |
| L3 | **Retrieval practice** | Recalling something (answering questions) strengthens memory more than re-reading it. | Roediger & Karpicke, 2006 | The questions are the core of the week, not the chat. The student answers; Prof AI doesn't answer for them. |
| L4 | **Useful feedback** | Feedback about the task and how to improve helps; praise of the person or a bare mark helps little. | Hattie & Timperley, 2007 | "Check my answer" says what to look at again, not just right or wrong. Praise effort and method, not the student. |
| L5 | **Productive struggle** | Some difficulty while learning (trying before being told) leads to better long-term learning. | Bjork, 1994; Kapur, 2008 | Let the student try first, then hint. Never hand over final answers. |
| L6 | **Self-explanation** | Students who explain each step to themselves learn more than those who don't. | Chi et al., 1989 | Ask "why does that step work?", especially at the stretch level. |
| L7 | **Step-based hints** | Tutoring that helps at each step of a problem gets close to the effect of a human tutor. | VanLehn, 2011 | Help is per step of the current question, not a whole worked answer. |
| L8 | **Manageable load** | Working memory is small. Too much new information at once blocks learning. | Sweller, 1988; Mayer, 2009 | One idea per message for beginners; short explanations; a question at a time. |
| L9 | **Spaced practice** | Practice spread over days beats the same practice crammed into one session. | Cepeda et al., 2006 | A weekly loop, with work between lessons. Later: bring back old topics. |
| L10 | **Interleaving** | Mixing problem types makes students choose the method, which improves transfer. | Rohrer & Taylor, 2007 | Later: mixed review questions across past lessons. |
| L11 | **Gaming the system** | Some students guess repeatedly or push for hints until they get the answer, and they learn less. | Baker et al., 2004 | Spot it (rapid guessing, begging for answers) and show the tutor. It's a signal about the student, not grounds to lock them out. |

## Where we stand

| Principle | Where we apply it | Status |
|-----------|-------------------|--------|
| L1 Worked examples | *Step by step* walks through the worked example first; worked examples are extracted from the tutor's material and stored with the lesson ([worksheet extraction](../features/2026-10-21-worksheet-extraction/plan.md)) | partly: the student page that leads with them is next |
| L2 Expertise reversal | Support levels per lesson: step by step, balanced, stretch | done |
| L3 Retrieval practice | Worksheet-first lessons: questions extracted from the tutor's worksheet ([worksheet extraction](../features/2026-10-21-worksheet-extraction/plan.md)); the student's question-by-question page is next | partly |
| L4 Useful feedback | "Check my answer" with feedback on the working | planned |
| L5 Productive struggle | Base prompt: try first, hints, never final answers (eval-tested) | done |
| L6 Self-explanation | *Stretch* level asks students to explain their reasoning | done |
| L7 Step-based hints | Base prompt and levels: one step or hint at a time; per-question help panel | partly: panel planned |
| L8 Manageable load | *Step by step*: one idea per message; short explanations; maths typeset rather than written as `(3x+2)/(x-1)` ([maths rendering](../features/2026-10-21-maths-rendering/plan.md)) | done |
| L9 Spaced practice | The weekly loop | partly: no spaced review yet |
| L10 Interleaving | Not yet | gap |
| L11 Gaming the system | Attempt counts in the tutor's progress view; help-seeking signals | planned |
