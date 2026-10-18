# Handover: Tutor chat PoC with per-user AI profiles

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-18

## What was built
- **Chat with Luna** (`gpt-5.6-luna`) at https://prof-ai.azurewebsites.net once the infra is deployed:
  - a conversation list, "New chat", streamed replies and a plain-text thread
  - Prof AI branding: mortarboard logo, navy and marigold palette, favicon, dark mode
  - a phone layout with a "Your chats" drawer
- **System prompt layers** (`prof_ai.chat.prompts.build_system_prompt`):
  1. Base tutor prompt: `src/prof_ai/chat/prompts/tutor.md`. It says to coach rather than give answers, and covers age-appropriate tone, scope, no personal details, and distress (trusted adult, Childline).
  2. Teaching style: `profiles/<tutor-id>/teaching-style.md`. A student gets their tutor's file; a tutor gets their own.
  3. Profile: `profiles/<user-id>/profile.md`.

  Each file is capped at 8 KB, and a missing file is skipped.
- **Per-user folders** in a new private Blob container, `profiles`. The web app can only read it; tutors write through the CLI.
- **Storage:** Cosmos containers `conversations` and `usage`, both partitioned by `/user_id`.
- **Limits** (all checked before any model call):
  - 2,000-character input; at most 1,000 output tokens with low reasoning effort; the last 20 messages sent; 200 messages per conversation
  - 50k tokens per user per day; 500k tokens per day across all users
  - `CHAT_ENABLED` kill switch
  - 10 messages a minute and one reply in flight per user (in-process)
- **Content-filter hits:** the reply is withheld and the user sees a neutral message. The user's message is stored as a flag on the conversation for the tutor.
- **CLI:** `prof profiles show|set`, `prof chats list|show`.
- **Verified locally against real Luna** with in-memory stores. Asked "just tell me the answer to 3x + 5 = 20", it coached step by step, applied the tutor's teaching style, and responded to the anxiety noted in the profile. Replies stream; the first text arrived after about 4 seconds.

**Differences from the plan:** none of substance. The flag stores the filtered user message so the tutor can see what triggered it.

## How to run / use it
1. **Deploy the infra first** (it adds the `profiles` container, its reader role, two Cosmos containers and the chat app settings): `bash scripts/deploy-infra.sh --what-if`, then without the flag. **Merging before this makes chat endpoints fail with 503/500**, because the Cosmos containers won't exist yet.
2. **Write profiles:**
   ```bash
   prof profiles set sam@example.com --teaching-style sam-style.md   # tutors: applies to you and your students
   prof profiles set alex@example.com --profile alex.md              # anyone: about this user
   prof profiles show alex@example.com                               # both files + the full system prompt
   ```
3. **Read transcripts:** `prof chats list alex@example.com`, then `prof chats show alex@example.com <conversation-id>`.
4. **Local:** set `FOUNDRY_ENDPOINT`, `CHAT_DEPLOYMENT` and `DEV_USER_ID` in `.env` (see `.env.example`), run uvicorn, then `cd web && npm run dev`. Each local message costs real tokens against your `az login`.
5. **Kill switch:** set the `CHAT_ENABLED` app setting to `false` in the portal (it takes effect on restart). A redeploy of the infra sets it back to `true`.

## Contracts other code can rely on
- **Blob:** `profiles/<user-id>/profile.md` and `profiles/<user-id>/teaching-style.md`. Use `prof_ai.profiles.store.ProfileStore`.
- **Prompt order:** base → tutor's teaching style → user profile. **Knowledge-base context and memory should be added as further sections in `build_system_prompt`**, after the profile.
- **Model:** `prof_ai.chat.model.ChatModel.stream(system_prompt, messages)` yields text deltas and then one `Usage`, and raises `ContentFilteredError` or `ModelUnavailableError`. `FoundryChatModel` uses the Foundry v1 OpenAI endpoint with an Entra token.
- **API** (all signed-in, scoped to the caller):
  - `GET /api/chat/conversations` → `[{id, title, updated_at}]`
  - `POST /api/chat/conversations` → 201 `{id, title, updated_at}`
  - `GET /api/chat/conversations/{id}` → `{id, title, updated_at, messages[{role, content, at}]}`; 404 if it isn't yours
  - `POST /api/chat/conversations/{id}/messages` `{content}` → `text/event-stream`, with events `delta {text}`, then `done {title}` or `error {message}`. Refusals happen before the stream as HTTP errors with `{detail}`: 400 (empty or too long), 404, 409 (chat full), 429 (rate or daily allowance), 503 (kill switch, global cap, store down, chat not configured).
- **Cosmos:**
  - `conversations`: `{id, user_id, title, messages[], input_tokens, output_tokens, flags[{kind, message, at}], created_at, updated_at}`
  - `usage`: `{id: "<user_id>:<YYYY-MM-DD>", user_id, date, tokens}` (UTC days)
- **A turn is saved only when complete.** The user message and the reply are saved together, and usage is recorded from the model's reported tokens.

## Tests added
- **`tests/tutor_chat/`** (38 tests):
  - prompt layering
  - Sam's and Punjy's students get different prompts
  - no cross-user profile leaks
  - profile size and emptiness checks
  - the SSE shape
  - the saved turn and its usage
  - conversation privacy (list, get and send)
  - history truncation
  - input caps
  - user and global budgets, yesterday's usage not counted
  - kill switch, rate limit, in-flight limit and its expiry
  - content-filter flag
  - model and store failures saving nothing
  - sign-in and locked accounts
  - the CLI
- **`web/src/sse.test.ts`** and **`web/src/api.test.ts`**: SSE parsing across split chunks, `sendMessage` streaming, error events, a stream that ends without finishing, and refusals.

## Known issues / TODOs
- **Not for real students yet.** The guard pipeline (Prompt Shields, topic relevance, a safeguarding flag to the tutor on self-harm categories, auto-lock), R16 data processing, parental consent and a retention policy must come first. It's tracked in INDEX.
- **Content-filtered and failed turns don't count towards the budget** (their usage isn't reported). The rate limit bounds this.
- **The rate limiter is in memory.** It resets on restart and assumes one instance (B1). Move it to Cosmos if we scale out.
- **The global cap is a cross-partition SUM per message.** That's fine at this scale; keep a running total document if usage grows.
- **Luna makes mistakes.** In an early test it gave a wrong hint for 7 × 8, so transcripts matter (R6).
- **The UI renders plain text only** (no Markdown or maths). Add a safe Markdown or KaTeX renderer later, kept within the CSP.
- **Titles** are the first 60 characters of the first message.

## For the other dev
After the infra deploy, ask Sam to make you a tutor (`prof users add --role tutor`) and write your own teaching style with `prof profiles set <you> --teaching-style style.md`. Your students then get your style automatically. Run `prof profiles show <email>` to see exactly what the model is told.
