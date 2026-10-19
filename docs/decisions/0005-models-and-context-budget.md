# 0005: Frontier models, a fixed context budget and tutor-led shared chats

- **Status:** accepted (2026-10-19, Sam); amended the same day: caps cut to fit the 50k tokens-per-minute quota (see the end). Built in stages: feature (a) context budget and memory, (b) lessons and tutor-created chats, (c) shared chat with `@AI`.

## Context
The chat sends a base prompt, the tutor's teaching style, the user's profile and the last 20 messages. Nothing counts tokens, nothing summarises, and the budget is in raw tokens, so a long chat silently forgets its start and burns the daily allowance faster with every turn. The next features add much more context: lesson material uploaded by the tutor, and knowledge-graph lookups. Without a fixed allowance per layer, those features can't know how much room they have, and one oversized upload would make every turn expensive and dilute the safety instructions.

We also want chats to change shape: a tutor sets each chat up for a lesson, the tutor and the student both write in it, and the AI only answers when called with `@AI`.

## Decision

### Models
- **Frontier models only**, with context windows of about 1M tokens (Luna, DeepSeek V4, GLM-5.x, Kimi K3 class). **Luna (`gpt-5.6-luna`) on Foundry stays the default.**
- **Prefer Foundry-hosted models**: managed identity, Foundry content filters, Microsoft's data processing terms, one bill. Ollama Cloud was considered and rejected for student data: US-hosted with no region pinning, no DPA or SLA on its pricing page, an API key instead of managed identity, and no content filter. Its flagship models also cost 5–15× Luna per token. It's fine for evals on synthetic data.
- Each model has a **profile** in code: deployment, context window, max output tokens, and prices per million tokens (input, cached input, output). Switching models is a config change plus a profile.

### Context stack
Ordered from most to least stable, because prompt caching matches an identical prefix. Caps are estimated tokens.

| # | Layer | Changes | Cap | Where it's enforced |
|---|---|---|---|---|
| 1 | Base safety prompt | never | 2k | in code |
| 2 | Tutor's teaching style | rarely | 3k | on save (8 KB) |
| 3 | **Lesson**: topics, objectives, tutor's notes, chapter text | per chat | **64k** | on upload and save |
| 4 | Student profile | rarely | 3k | on save (8 KB) |
| 5 | Conversation summary | every few turns | 4k | when summarising |
| 6 | Recent messages | every turn (append) | 32k | when assembling |
| 7 | **Reference material** from the knowledge graph | every turn | **64k** | in the retriever and when assembling |
| 8 | The new message | every turn | 3k | input cap (2,000 chars; multi-byte characters estimate higher) |
| 9 | Trailing safety reminder | never | 0.5k | in code |

- **Input total:** 175.5k at most. **Output reserve:** 8k (reasoning plus reply). **Design ceiling: 256k**, about a quarter of the window, leaving ~72k headroom for token-estimate error. Staying well under the window also keeps us clear of long-context price tiers, and keeps the safety instructions from being diluted.
- **Reference material sits after the recent messages**, attached to the current turn and not kept in history. The history then only ever grows by appending, so the cached prefix survives from turn to turn.
- **Lesson and reference text are labelled as reference material, not instructions** (indirect prompt injection, R23).
- **The safety rules sit at both ends**: the base prompt first and a short reminder last.
- Typical turns are far below the caps. Caps are ceilings, not targets.

### Enforcement: four gates
1. **Startup:** the app refuses to start if the layer caps plus the output reserve exceed the 256k ceiling, or the ceiling exceeds the active model's context window.
2. **Write time:** anything stored as context is measured when it's saved. A lesson's uploads are extracted and counted once, and the tutor sees a meter. A save over 64k is refused, and the tutor picks pages or sections; the rest can go to the knowledge graph. Profiles and teaching styles keep their 8 KB caps.
3. **Read time:** the knowledge graph's retriever takes a token budget and returns whole snippets, best first, until it's full. Snippets have a maximum size fixed at indexing, so no single one can blow the budget.
4. **Assembly:** the assembler measures every layer before calling the model. If a layer is over its cap, it trims in a fixed order: lowest-ranked reference snippets, then the oldest recent messages. It never trims the base prompt, the reminder or the lesson. If the fixed layers alone are over (a bug), the turn is refused (fail closed). Each turn records its per-layer sizes and the model-reported tokens.

**Token counting** is a conservative estimate (UTF-8 bytes ÷ 3; English averages about 4 characters per token), so it works for any model and needs no tokenizer download. Each turn logs the estimate next to the model's reported input tokens, so we can check the margin.

### Memory
- **A window counted in tokens:** the newest messages that fit in 32k, instead of the last 20.
- **A rolling summary:** once the messages that have fallen out of the window reach a threshold, one model call folds them into the existing summary (≤4k). The summary focuses on learning: what's been covered, what the student finds hard, and what was agreed. It's stored on the conversation and visible to the tutor.
- Summary calls go through `ChatService` like any other model call: kill switch, budgets and the content filter apply. No memory framework: the logic is small, and a framework would add dependencies (R19) and a second path to the model.

### Budgets in money
- Every turn's cost is computed from the model profile's prices and the reported input, cached input and output tokens.
- A **per-student daily budget** ($0.50) and a **global daily cap** ($1.50), both in USD. Luna's price was checked against our October bill: $0.20 input and $1.20 output per million tokens (Global Standard, short context). **Tutors are exempt from the per-user budget** but count towards the global cap, and the kill switch and rate limits still apply to them.
- Cached input is cheap, so a large, stable lesson costs far less per turn than its size suggests.

### Chats (features b and c)
- **Only tutors create chats.** Each chat belongs to **one student and their tutor** and is set up for one lesson.
- **At most 5 chats per student.** The tutor deletes one to free a slot.
- **Shared chat:** the student and the tutor both write in it. **The AI replies only to messages that mention `@AI`**, from either of them. Messages without `@AI` don't call the model.
- **Authorship is set by the server** (student, tutor or AI) and shown to the model with labels the student can't forge (R25).

## Alternatives considered
- **Design to the full ~1M window.** Whole books would fit in the prompt, but every turn would cost up to ~$0.20 on Luna before caching. Instruction-following also drops well before the window is full: in NoLiMa (2025), most models fell below half their short-context accuracy by 32k. Rejected.
- **A 128k ceiling, so smaller open models like gpt-oss stay an option.** Not needed, since we're committing to frontier models, and it leaves the knowledge graph only ~16k. Rejected.
- **Exact token counting with `tiktoken`.** It's specific to the model family and downloads encoding files at first use. A conservative estimate plus headroom is enough. Rejected for now.
- **A memory framework** (Semantic Kernel chat-history reducers, LangChain/LangGraph memory, Mem0, Letta). Rejected: see Memory.
- **Ollama Cloud.** Rejected for student data: see Models.

## Consequences
- Lesson setup (b) and the knowledge graph each have a fixed, enforced allowance to design against: 64k each.
- The tutor has to choose what goes into a lesson when the material is large.
- Budgets become dollars a day. Existing `usage` documents keep their token counts; new ones add cost.
- A dilution eval is needed before we trust the 64k lesson cap: run the safety and coaching scenarios with the lesson filled to 16k, 32k and 64k, and lower the cap if behaviour slips.
- A smaller-window model would fail the startup check rather than silently truncating prompts.
- Shared chats bring one-to-one adult–child messaging onto the platform (R24). That's better than WhatsApp because it's logged, but it needs a retention policy and safeguarding review before real students.

## Amendment (2026-10-19): caps fit the tokens-per-minute quota

**What we found.** The dilution eval ([handover](../features/2026-10-19-context-dilution-eval/handover.md)) showed two things:
- **Dilution isn't a limit up to 40k.** With the hardened base prompt, all 10 scenarios passed 3/3 with the lesson at 2k, 16k, 32k and 40k.
- **Throughput is the real limit.** Azure counts every request's full estimated prompt plus `max_tokens` against the deployment's tokens per minute, cached or not.
  - The Luna deployment had 10k a minute; it's now 50k, which is the most our quota allows (the football project holds 200 of 250).
  - The original caps add up to about 180k, so a fully loaded turn could never be accepted.

**Decision, until the quota grows:**
- **New caps:**

  | Layer | Was | Now |
  |---|---|---|
  | Lesson | 64k | **12k** |
  | Recent messages | 32k | **12k** |
  | Reference material | 64k | **4k** |
  | Model output | 4,000 | **1,500** |

  The other layers are unchanged. Real replies peaked at 174 tokens in the eval.
- **Largest possible turn:** 43.5k input plus 1.5k output, which fits 50k.
- **A new startup check:** layer caps plus the model's output cap must fit `CHAT_TOKENS_PER_MINUTE`, which Bicep sets from the deployment's capacity. The 256k ceiling stays as the outer design bound.
- **Raising the caps when quota grows:**
  1. Raise `chatModel.capacity`.
  2. Raise `LAYER_CAPS` (lessons up to 40k are already eval-backed).
  3. Re-run `prof eval dilution` for anything above 40k.

  The quota-increase form is https://aka.ms/oai/stuquotarequest.

**Consequences:**
- A 12k lesson is about 6,000 words, or 12–15 textbook pages: a short chapter or the key sections of a long one. Tutors pick sections for bigger material.
- The knowledge graph gets 4k per turn for now: a handful of snippets.
- Even well under the caps, 50k a minute is shared by everyone; a 20k turn uses 40% of it.
