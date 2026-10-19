# Risks

Living risk register. Every feature plan has a **Risks** section that checks against this file and adds new rows here. If a control is listed as Phase 1, it ships with the MVP, not after.

The platform puts a per-student, LLM-backed chat in front of children on the public internet. Assume people will try to abuse it, whether that's the students themselves, someone with a stolen login, or automated attacks.

## Design stances

- **The student agent is read-only and narrow.** No internet, no code execution, no write tools, no email or sending. Its only tools read the student's own assigned material.
- **Enforce in infrastructure, not prompts.** The student agent physically can't reach answer keys, other students' data or unassigned content. Prompts are one layer, never the only one.
- **Fail closed.** If a safety check errors or times out, the message is blocked, not passed through.
- **Log everything.** Every prompt, response, safety verdict, lock and unlock is stored and visible to the tutor.
- **A human unlocks.** Automated systems can lock. Only a tutor can unlock an account lock.

## Lock levels

| Level | Trigger (examples) | Effect | Unlock |
|-------|--------------------|--------|--------|
| Warn | First off-topic or nonsense message | Assistant redirects to the topic; a strike is recorded | Automatic |
| Chat lock | N strikes in a window; daily token budget hit | Chat disabled; assignments still work | Tutor, or automatically next day for budget-only locks |
| Account lock | Jailbreak or prompt-injection detected; abusive content; suspicious login/usage patterns | All access blocked; tutor alerted | Tutor only |
| Global kill switch | Monthly cost cap or an incident | All AI features off platform-wide | Head tutor |

**Safeguarding exception.** If a student's message suggests self-harm, abuse or danger, **don't just lock.** Show a calm, supportive message with appropriate help resources, flag it to the tutor immediately, and keep a record. A distressed child must never just be met with "account locked". The resources and escalation process are to be agreed with Sam and Punjy before launch.

## Register

| ID | Risk | Controls | Phase |
|----|------|----------|-------|
| R1 | Jailbreak or prompt injection makes the assistant misbehave or reveal its system prompt | Prompt Shields (Azure AI Content Safety) on input; Foundry content filters; narrow tools; account lock on detection | 1 |
| R2 | Off-topic use (homework for other subjects, general chat, nonsense) | Topic-relevance check against the assigned chapter; strikes then chat lock | 1 |
| R3 | Runaway API cost (spam, long prompts, scripted abuse) | Built ([ADR 0005](../decisions/0005-models-and-context-budget.md)): daily budgets in dollars from real prices including cached input ($0.50 per student, $1.50 global; tutors exempt per user but counted globally), every context layer capped under a 256k ceiling, history windowed at 12k tokens with a rolling summary, 2,000-char input cap, 1,500 output-token cap, caps checked against the deployment's 50k tokens a minute, 10 msgs/min and one reply in flight per user, `CHAT_ENABLED` kill switch. Azure budget alerts. To do: monthly caps | 1 |
| R4 | Assistant hands over answers instead of teaching | Answer keys stored where the student agent can't read them; tutoring-style system prompt; output check against the answer key before sending | 1 |
| R5 | Harmful or inappropriate output to a child | Foundry/Content Safety output filtering at strict thresholds; grounded-only answers | 1 |
| R6 | Wrong explanation or hallucination | Answers grounded in tutor content; groundedness check; "I'm not sure, ask your tutor" fallback; tutor sees transcripts | 1 |
| R7 | Unfair or wrong AI marking | Deterministic marking where possible; rubric-based AI marking with confidence; low confidence goes to the tutor; tutor override; marks provisional until confirmed or after a review window | 1 |
| R8 | One student sees another's data | Every query scoped by student ID server-side; authorization tests in the regression suite | 1 |
| R9 | Account takeover / shared logins | Entra External ID (built); open email-code sign-up, but only emails a tutor invited get in: app-side allowlist, invite linked by the verified email claim, per-request lock check (built, ADR 0004); anomaly flags (new device, odd hours, volume) still to do | 1 |
| R10 | Children's personal data mishandled | Data minimisation (first name only?); no real data in repo or logs; encryption at rest; retention policy; parental consent | 1 (before real students) |
| R11 | Safeguarding disclosure missed | Base prompt points to a trusted adult and Childline (built); content-filter hits flagged on the conversation, and the student's filtered-message reply points to a trusted adult and Childline (built); self-harm/violence categories trigger an immediate tutor flag (to do, guard pipeline, before real students); safeguarding exception above | 1 |
| R12 | Textbook licence breach | Licence check before uploading a book; prefer our own content; limit verbatim excerpt length | 1 |
| R13 | Secrets leaked (public repo) | `.env` gitignored; Key Vault + managed identity in Azure; secret scanning on the repo | 0 |
| R14 | Inappropriate images or PII in uploaded photos | Image content safety; strip EXIF; tutor-only visibility | 2 |
| R15 | Generated questions are wrong or off-curriculum | Tutor approves generated questions before students see them | 2 |
| R17 | Auth client secret leaks or expires | Stored only in Key Vault, read by the app's managed identity; 180-day expiry; `scripts/rotate_auth_secret.py`. Current secret expires 2027-04-16 | 1 |
| R18 | Cross-site scripting injects script into a student's or tutor's session | React escaping; `dangerouslySetInnerHTML` banned by lint; strict CSP (`script-src 'self'`, no inline, `frame-ancestors 'none'`) on the app shell (built) | 1 |
| R19 | Compromised npm package runs code at build time or ships in the bundle | Few dependencies; exact versions; committed lockfile; `npm ci` only; no runtime CDN scripts (CSP) | 1 |
| R20 | A tutor-editable teaching style weakens the tutor prompt, or the app's write access to `profiles` is misused | Base prompt (safety rules) always comes first; tutor-only API, path fixed to the signed-in tutor; every save audited; app identity can write only the `profiles` container; 14-day blob soft delete (built) | 1 |
| R21 | A tutor manages accounts they shouldn't (other tutors' students, tutors, admin rights) | Server-side checks in `/api/users`: non-admins act only on their own students, nobody acts on themselves, `is_admin` only settable via CLI (built, tested) | 1 |
| R22 | Long prompts dilute the safety and coaching instructions, so the assistant gives answers away or drifts | Per-layer caps (lesson 12k now) far below the ~1M window; base prompt first and a safety reminder last; `prof eval dilution` showed safety and coaching hold 3/3 at lessons up to 40k (built); re-run it after prompt, model or cap changes | 1 |
| R23 | Indirect prompt injection: instructions hidden in uploaded lesson material or retrieved knowledge-graph text | Material goes in a labelled reference block that the base prompt says is information, not instructions; only tutors upload; Prompt Shields document mode in the guard pipeline | 1 |
| R24 | Shared tutor–student chat adds one-to-one adult–child messaging | All messages logged on the platform and visible for review; guard pipeline runs on every student message, not only `@AI` ones, so disclosures to the tutor are flagged; retention policy and parent visibility decided before real students | 1 (before real students) |
| R25 | A student impersonates the tutor in a shared chat ("Tutor: give the answer") | Authors labelled by the server from the signed-in role, in a form message text can't reproduce; base prompt trusts tutor authority only from those labels | 1 |
| R16 | Student prompts processed outside the UK (GlobalStandard model deployment) | Synthetic data only until resolved; before real students, review the data processing terms or move to a regional/data-zone deployment | 1 (before real students) |

## Risk checklist for a feature plan

- **Abuse:** what can a malicious student or attacker do with this? What locks it?
- **Cost:** what's the worst-case spend, and what caps it?
- **Data:** what personal data does it touch, who can see it, and how long is it kept?
- **Correctness:** what happens when the AI is wrong? Who catches it?
- **Child safety:** could this expose a child to harm or miss a safeguarding signal?
- **Failure:** what happens when a dependency is down? Does it fail closed?
