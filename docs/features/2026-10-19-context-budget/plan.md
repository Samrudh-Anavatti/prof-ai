# Plan: Context budget, conversation memory and money-based budgets

- **Owner:** sam
- **Branch:** `sam/context-budget`
- **Date:** 2026-10-19

## Goal
Make the prompt a controlled, measured thing before lessons and the knowledge graph add to it. This is feature (a) of [ADR 0005](../../decisions/0005-models-and-context-budget.md):
- every model call is built by one assembler from capped layers, in a cache-friendly order;
- long chats keep their memory through a token-budgeted window and a rolling summary;
- budgets are in dollars, so cached input and model choice count properly, and tutors aren't limited per user.

Lessons (b) and shared chats (c) are separate features. This one leaves the lesson and reference layers as empty inputs that those features fill.

## Approach
- **Model profiles** (`chat/model_profiles.py`): `ModelProfile(deployment, context_window, max_output_tokens, input_usd_per_m, cached_input_usd_per_m, output_usd_per_m)`. Luna's profile is the only one for now. The active profile is chosen by `CHAT_DEPLOYMENT`, and an unknown deployment fails at startup.
- **Context budget** (`chat/context.py`):
  - `estimate_tokens(text)`: UTF-8 bytes ÷ 3, rounded up.
  - `LAYER_CAPS` and `OUTPUT_RESERVE` as in the ADR, and `CONTEXT_CEILING = 256_000`.
  - `check_budget(profile)`, called by `create_app`, raises if the caps plus the reserve exceed the ceiling, or the ceiling exceeds the model's window.
  - `assemble(...)` takes the layers as plain inputs (base, style, lesson, profile, summary, history, reference snippets, new message). It returns the model messages plus a ledger of per-layer estimates. Over-cap history is trimmed oldest-first and over-cap references lowest-ranked-first. If a fixed layer is over its cap, `ContextOverflowError` refuses the turn.
  - **Message order:** one system message (base → style → lesson → profile → summary), then the history, then the new user message with any reference material in a labelled block, then a short system reminder.
- **Memory** (`chat/memory.py`):
  - The history window is the newest messages that fit in 32k (no longer 20 messages).
  - When the unsummarised messages before the window reach 8k estimated tokens, a summary call folds them into `conversation.summary` (≤4k) using `prompts/summarise.md`. It runs after the reply is saved and before `done`, so the user never waits for it before seeing the reply.
  - A failed or filtered summary is logged and retried on the next turn; the turn itself still succeeds. The window keeps working without a summary.
- **Money budgets:**
  - `Usage` gains `cached_input_tokens` (from the model's `prompt_tokens_details.cached_tokens`) and a `cost_usd(profile)`.
  - The `usage` document gains `cost_micro_usd`, an integer to avoid float drift, alongside `tokens`.
  - New settings `CHAT_DAILY_USER_USD` (0.20) and `CHAT_DAILY_GLOBAL_USD` (1.25) replace the token settings. Tutors skip the per-user check but still add to the global total.
  - Summary calls are charged to whoever sent the message that triggered them.
- **Ledger:** each assistant message stores a `context` record with the per-layer estimates, the estimated total, and the reported input, cached and output tokens and cost. This lets us check the estimator, and later lets tutors see what the AI saw.
- **Model client:** `ChatModel.stream(messages)` takes the assembled list of `PromptMessage(role: system|user|assistant, content)`. The output cap comes from the profile (4,000 tokens, which includes reasoning; replies are still asked to be short).
- **CLI:** `prof chats show` prints the summary and each turn's context sizes.

## Risks
| Risk | Control in this feature |
|------|------|
| **R3 cost** | Budgets in dollars, from real prices and the reported cached tokens. Per-student daily budget (tutors exempt) and a global daily cap that includes tutors and summaries. Every layer is capped, the output cap comes from the profile, and the kill switch and rate limits are unchanged. **Worst case** at full caps on Luna: 173.5k input and 4k output is about $0.04 a turn uncached. The global cap of $1.25 a day (≈£30 a month) keeps the model well inside the £50 budget alongside App Service. |
| **R22 long context dilutes safety rules** (new) | Caps under a 256k ceiling; base prompt first and a reminder last; lesson and reference text labelled as material, not instructions. The dilution eval (a separate INDEX row) comes before we rely on the 64k lesson cap. |
| **R23 indirect prompt injection** (new) | Lesson and reference text go into a labelled block, and the base prompt says documents are information, not instructions. Only tutors write lessons. Prompt Shields' document mode comes with the guard pipeline. |
| **Estimator undercounts** | Bytes ÷ 3 overestimates English text. The ~75k headroom absorbs error. The ledger records estimated against reported tokens. If the model still rejects the prompt as too long, the turn fails with "unavailable" and nothing is saved. |
| **R6 / R10 summary is wrong or keeps personal details** | The summary prompt keeps it to learning progress and says not to record personal details. It's stored on the conversation (so deleting the user erases it, with no new container) and visible to the tutor. The full transcript is kept, so the summary never replaces the record. |
| **Summary as a cost or abuse lever** | One summary call at most per turn, only past the 8k threshold, with a capped output. It goes through the same budgets, kill switch and content filter. |
| **Tutor exemption** | A compromised tutor account is still bound by the global cap, the rate limit, one reply in flight and the kill switch. |
| **Failure** | Unknown model or caps over the ceiling: the app won't start. Fixed layer over its cap: the turn is refused (503 "unavailable") and logged. Budget read fails: refused (fails closed), as today. |

## Files / modules touched
- **New:**
  - `src/prof_ai/chat/model_profiles.py`, `chat/context.py`, `chat/memory.py`, `chat/prompts/summarise.md`
  - `tests/context_budget/`
- **Changed:**
  - `chat/service.py` (assembly, memory, money budgets), `chat/model.py` (`PromptMessage`, profile output cap, cached tokens), `chat/models.py` (`summary`, `summarised_count`, `context` ledger, `Usage.cached_input_tokens`), `chat/prompts.py` (returns layers instead of one string), `chat/prompts/tutor.md` (reference-material rule)
  - `chat/store.py`, `chat/cosmos_store.py` (cost methods), `config.py`, `main.py`, `cli.py`
  - `.env.example`, `infra/main.bicep` (app settings)
  - `tests/tutor_chat/` and `tests/user_admin/`: these are Sam's own tests, updated where they pin the replaced contracts (the 20-message window and token budgets)
  - docs: ADR 0005, INDEX, `risks.md`, `architecture.md`, `CLAUDE.md` (context rule), README at merge

## Contracts added or changed
- **Every model call goes through `ChatService`, using `chat.context.assemble`.** Feature (b) passes the lesson text and the knowledge graph passes reference snippets. Neither builds prompts itself.
- **`LAYER_CAPS`** (estimated tokens): base 2k, style 3k, lesson 64k, profile 3k, summary 4k, history 32k, reference 64k, message 1k, reminder 0.5k. `OUTPUT_RESERVE` 8k, `CONTEXT_CEILING` 256k. Feature (b) enforces the lesson cap at save time using `estimate_tokens`. The knowledge graph's retriever takes `max_tokens` and returns whole snippets, best first.
- **`ChatModel.stream(messages: Sequence[PromptMessage]) -> Iterator[str | Usage]`.** `Usage` gains `cached_input_tokens`.
- **Cosmos:**
  - `conversations` gains `summary: str`, `summarised_count: int`, and on assistant messages `context: {layers: {name: tokens}, estimated_input, input_tokens, cached_input_tokens, output_tokens, cost_micro_usd}`.
  - `usage` gains `cost_micro_usd`. `tokens` stays for reference.
- **Store methods:** `cost_used(user_id, day)`, `cost_used_by_everyone(day)` and `add_usage(user_id, day, tokens, cost_micro_usd)` replace `tokens_used`, `tokens_used_by_everyone` and `add_tokens`.
- **App settings:** `CHAT_DAILY_USER_USD` and `CHAT_DAILY_GLOBAL_USD` replace `CHAT_DAILY_USER_TOKENS` and `CHAT_DAILY_GLOBAL_TOKENS`.
- **API:** unchanged. The 429 and 503 refusal messages stay the same.

## Tests to add
`tests/context_budget/`, offline with a fake model, in-memory stores and a fixed clock:
- the default caps fit the ceiling, and the startup check fails for a small window or oversized caps
- an unknown deployment fails at startup
- assembled order: system layers, history, the new message with references, then the reminder; the stable prefix is identical across two turns of the same chat
- history window: token-based, newest kept, and a long old message doesn't push out recent ones beyond the cap
- reference snippets trimmed lowest-ranked first; a fixed layer over its cap refuses the turn with nothing saved and no model call
- summary: triggered only past the threshold; it folds in the previous summary; `summarised_count` advances; a failed summary doesn't fail the turn and is retried next turn; summary usage is charged
- money: cost from the profile prices including cached tokens; the student budget refuses; a tutor over the student budget is allowed; tutor and summary spend counts towards the global cap; yesterday's spend isn't counted
- the ledger is saved on the assistant message
- deleting a user erases the summaries with their conversations
- CLI `chats show` prints the summary and context sizes

## Open questions
- **Luna's real prices**, especially cached input. Trackers disagree ($0.20/$1.20 against $1/$6). Before merge, check Cost Management against our `usage` records and set the profile from that.
- **Budget numbers:** $0.20 per student a day (~5 full-load turns, or dozens of typical ones) and $1.25 a day globally are starting points.
- **Output cap:** 4,000 tokens including reasoning. Is that enough for Luna at low effort without truncation?
- **Summary threshold** (8k) and summary size (4k): tune them from the ledger.
