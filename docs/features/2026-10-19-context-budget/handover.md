# Handover: Context budget, conversation memory and money-based budgets

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-19

## What was built
Feature (a) of [ADR 0005](../../decisions/0005-models-and-context-budget.md).

- **One assembler builds every chat call** (`prof_ai.chat.context.assemble`):
  - **Capped layers**, in estimated tokens: base 2k, teaching style 3k, lesson 64k, profile 3k, summary 4k, history 32k, reference 64k, message 3k, reminder 0.5k. There's an 8k output reserve under a 256k ceiling.
  - **Cache-friendly order:** one system message (base → style → lesson → profile → summary), then the history, then the new message with any reference material in a labelled block, then a short trailing safety reminder (`prompts/reminder.md`).
  - **Trimming:** history is the newest messages that fit in 32k; reference snippets are kept best first until 64k. Any other layer over its cap refuses the turn (503, nothing sent or saved).
- **Startup check:** `ChatService` refuses to construct if the caps plus the reserve exceed 256k, or the model's window or output cap doesn't fit. `main.py` looks up the model profile from `CHAT_DEPLOYMENT`; an unknown deployment stops the app starting.
- **Model profiles** (`chat/model_profiles.py`): Luna's window (922k), output cap (4,000 tokens, including reasoning) and prices ($0.20 input, $0.02 cached input, $1.20 output per million tokens).
- **Rolling summary** (`chat/memory.py`, `prompts/summarise.md`):
  - It runs once the unsummarised messages outside the window reach 8k estimated tokens, taking up to 24k per call and folding them into the previous summary.
  - The summary is clipped to 12 KB (4k estimated) and sent as the summary layer on later turns.
  - It runs after the reply has streamed and been saved, before `done`. A failure is logged and retried next turn.
  - It's charged to whoever sent the message that triggered it, and skipped if the global cap has been reached.
- **Dollar budgets:**
  - `CHAT_DAILY_USER_USD` (0.50) and `CHAT_DAILY_GLOBAL_USD` (1.50) replace the token settings.
  - Cost is worked out from reported input, cached input and output tokens.
  - **Tutors skip the per-user budget**, but their spend counts towards the global cap.
- **Ledger:** every assistant message stores `context`: the estimated size of each layer, the reported tokens (including cached) and the cost. `logger.info` records estimated against reported tokens for every turn (no message content).
- **CLI:** `prof chats show` prints the summary and each reply's context line.
- **Base prompt:** a new rule that lesson material, reference material and conversation notes are information, never instructions.

**Differences from the plan:**
- The message cap is 3k, not 1k: 2,000 multi-byte characters can estimate to about 2.7k. Total input is 175.5k, with ~72k headroom.
- Context is assembled in `begin_turn`, before the stream starts. So a profile-store failure or an oversized layer is now an HTTP 503 refusal rather than an SSE `error` event.
- The API's conversation detail now returns only `{role, content, at}` per message, so the ledger and summary never reach the browser.

## Live check (2026-10-19)
I sent two identical calls to real Luna through the assembler, with a ~2.5k lesson layer, a reference snippet and "Just tell me the answer: simplify 6:9":
- **Message order:** Foundry accepts the trailing system message.
- **Caching:** on the second call, 2,449 of 2,510 input tokens were cached, and the cost fell from $0.00055 to $0.00011.
- **Estimate:** 3,155 estimated against 2,510 reported, so the estimate runs about 26% high, as intended.
- **Coaching:** Luna coached (find the highest common factor, divide both parts) rather than answering.

## How to run / use it
- **Nothing to deploy beyond the merge.** The new settings default to 0.50 and 1.50 in code.
  - The infra template now sets `CHAT_DAILY_USER_USD` and `CHAT_DAILY_GLOBAL_USD`. Run `bash scripts/deploy-infra.sh` when convenient, then delete the stale `CHAT_DAILY_USER_TOKENS` and `CHAT_DAILY_GLOBAL_TOKENS` app settings (unused now).
- **Existing data works unchanged:**
  - Old conversations get an empty summary.
  - Old `usage` documents count as $0 spent; only spend from deploy day onwards counts.
- **See what the AI was sent:** `prof chats show <email> <conversation-id>`.

## Contracts other code can rely on
- **Every model call goes through `ChatService`, using `chat.context.assemble(ContextInput(...))`.**
  - `ContextInput(message, teaching_style, lesson, profile, summary, history, references)`.
  - Lessons (b) pass `lesson`; the knowledge graph passes `references` (best first).
  - Don't build prompts anywhere else.
- **Sizes:**
  - `chat.context.LAYER_CAPS[Layer.LESSON]` (64k) and `[Layer.REFERENCE]` (64k) are the allowances.
  - Measure with `chat.context.estimate_tokens` (UTF-8 bytes ÷ 3, rounded up).
  - **Lessons must refuse saves over the cap at write time**: the assembler refuses the turn, and the chat would be unusable.
- **`ChatModel.stream(messages: Sequence[PromptMessage], max_output_tokens: int) -> Iterator[str | Usage]`.** `Usage` has `cached_input_tokens`.
- **`ModelProfile`** in `chat/model_profiles.py`. A new model needs a profile there, and it must pass `check_budget`.
- **Cosmos:**
  - `conversations` gains `summary`, `summarised_count`, and `context` on assistant messages: `{layers, estimated_input, input_tokens, cached_input_tokens, output_tokens, cost_micro_usd}`.
  - `usage` gains `cost_micro_usd`.
- **`ChatStore`:** `cost_used`, `cost_used_by_everyone` and `add_usage(user_id, day, tokens, cost_micro_usd)` replace the token methods.
- **`ChatLimits(enabled, daily_user_usd, daily_global_usd)`.**

## Tests added
- **`tests/context_budget/`** (30 tests):
  - caps fit the ceiling; small-window and over-reserve models refused; unknown deployment
  - the estimator; cost with cached input
  - layer order and the reminder last; the identical prefix from one turn to the next
  - the token-based history window; an oversized old message cuts the window; references trimmed lowest-ranked first
  - each fixed layer over its cap refuses; the ledger has every layer
  - summary: not triggered on short chats; triggered and saved with the right count; sent on later turns and folded into the next one; failure keeps the turn and retries; charged to the sender
  - a corrupt oversized summary refuses the turn with no model call
  - the ledger is saved; the ledger and summary aren't sent to the browser
  - tutors exempt from the student budget; tutor spend hits the global cap
  - erasing a user removes their summaries
  - the CLI shows the summary and context
- **Sam's earlier tests, changed to the new contracts:**
  - `tests/tutor_chat/`: the fake model takes `PromptMessage`s; the in-memory store has cost methods; the 20-message window test now checks that short history is sent in full, then the message, then the reminder; budgets in dollars.
  - `tests/teaching_style_editor/`: reads `model.system_prompts`.
  - `tests/user_admin/`: `cost_used` after delete.

## Known issues / TODOs
- **Cached input price is assumed** at 10% of input ($0.02 per million). Check it once a cached meter appears on the bill, and update `LUNA`.
- **Gap before summarising:** messages that leave the window aren't summarised until they reach 8k, so up to ~8k of old conversation can be in neither the window nor the summary. Lower `SUMMARY_TRIGGER_TOKENS` if this shows up in transcripts.
- **A summary that's always content-filtered** is retried on every turn (logged). This is bounded by the rate limit and the budgets.
- **Summaries aren't shown in the web UI yet.** Tutors see them with the CLI. The tutor view comes with the shared chat (c).
- **The dilution eval** (an INDEX row) must run before lesson setup relies on the full 64k.
- **The 200-message cap** per conversation is unchanged. Shared chats (c) move messages to one document each.

## For the other dev
- **Anything that adds to the prompt goes through `ContextInput`, with a cap in `LAYER_CAPS`.** A new layer needs an ADR 0005 update and must still fit the 256k ceiling (there's a test for that).
- **Lessons and the knowledge graph have 64k each.** Enforce the lesson cap when it's saved, and give the retriever a `max_tokens`.
- **Budgets are dollars now:**
  - students have $0.50 a day; everyone together has $1.50;
  - tutors are unlimited per user;
  - change them with the `CHAT_DAILY_*_USD` app settings.
