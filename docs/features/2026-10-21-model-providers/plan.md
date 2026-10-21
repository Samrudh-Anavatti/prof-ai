# Plan: Model providers and a model picker

- **Owner:** punji
- **Branch:** `feat/model-providers`
- **Date:** 2026-10-21

## Goal
Prof AI shouldn't depend on one provider. Build the plumbing to use any provider with an OpenAI-compatible API, start with Ollama Cloud, and let tutors pick a model per lesson, seeing what each one costs and how well it has been tested.

Student data stays where ADR 0005 put it. Each model says whether it's `approved_for_student_conversations`. Only approved models run in a chat that belongs to a student. Others are for tutors' own test chats, evals, and later for tutor-content work such as extracting questions from a worksheet.

## Approach
- **One adapter:** `OpenAIChatModel` in `chat/model.py` takes an OpenAI client, a model name and how that API names the output cap. `foundry_chat_model` (managed identity, `max_completion_tokens`) and `ollama_chat_model` (API key, `https://ollama.com/v1`, `max_tokens`) build it. Adding a provider is a factory plus profiles.
- **Profiles say more:** `ModelProfile` gains `provider`, `label`, `approved_for_student_conversations` (default `False`, so a new model is never approved by accident) and `notes` (what tutors see about quality and testing). Luna is approved.
- **First Ollama models:** `glm-5.3-flash` ($0.15 / $0.03 / $0.50 per million input / cached / output) and `deepseek-v4.1-flash` ($0.30 / $0.006 / $1.20), at peak prices from ollama.com/pricing on 2026-10-21. Both have 1M-token windows, so they pass ADR 0005's startup check unchanged (`gpt-oss:120b` has 128k, so it doesn't). Both accept images. They're only registered when `OLLAMA_API_KEY` is set.
- **A registry in `ChatService`:** the default model (from `CHAT_DEPLOYMENT`, checked against `CHAT_TOKENS_PER_MINUTE`) plus extras, each passing `check_budget`. Ollama has no tokens-per-minute quota, so that part of the check is skipped for it.
- **Which model a turn uses:** the conversation's `model` if set, otherwise (for a tutor's own chat) the tutor's preferred model, otherwise the default. Summaries and costs use the same model. A chat that belongs to a student only ever runs on an approved model: setting an unapproved one is refused (400), and the turn refuses (fail closed) if one somehow gets there.
- **Tutor's preferred model:** `User.preferred_model`, set with `PUT /api/models/preferred` (tutors only, audited). It applies to the tutor's test chats and is pre-selected for new lessons.
- **Picker:** `GET /api/models` (tutors only) lists each model's label, provider, approval, prices, context window, an estimated cost per typical message and the notes. The Lessons page gets a model choice on the form and on each chat row, plus "Your default model". Unapproved models are shown, but disabled for students.
- **Key:** Punji stores the Ollama key in Key Vault as `ollama-api-key` with a command that never echoes it. Bicep adds `OLLAMA_API_KEY` as a Key Vault reference. An unresolved reference counts as no key.
- **Evals:** `prof eval dilution --model <id>` runs the eval on any registered model, so a model can earn approval or better notes.

## Learning check
No direct effect on learning. Weaker models could teach worse (L5, L7). Notes show each model's eval results, and only approved models reach students.

## Risks
- **R16 / R10 (student data outside the UK, no data agreement):** Ollama is US-hosted with no DPA. Controls: `approved_for_student_conversations=False`, enforced server-side when a model is set and on every turn; only tutors' own chats can use it.
- **R5 / R11 (no content filter on Ollama):** Foundry's filters don't apply. The same controls keep it away from students. Before approving any non-Foundry model, the guard pipeline (our own Content Safety calls) must cover it.
- **R3 (cost):** every model has real per-token prices, so dollar budgets still work. Tutors are exempt per user but count globally, as before. Prices use peak rates (conservative).
- **R13 (secrets):** the key lives only in Key Vault, read through an App Service reference. It's never in the repo or in front of the agent.
- **R22 (dilution):** a model's notes say whether it passed `prof eval dilution`. Approval needs a pass plus the data-residency bar.
- **Failure:** an Ollama outage or a 401 becomes `ModelUnavailableError` and the usual "unavailable" message.

## Files / modules touched
- `src/prof_ai/chat/`: `model.py`, `model_profiles.py`, `service.py`, `api.py`, new `models_api.py`
- `src/prof_ai/users/models.py` (`preferred_model`), `src/prof_ai/lessons/api.py`, `src/prof_ai/config.py`, `src/prof_ai/main.py`, `src/prof_ai/cli.py`
- `infra/main.bicep` (Key Vault reference)
- `web/src/`: `api.ts`, `LessonsPage.tsx`, `lessons.ts`
- Docs: ADR 0005 amendment, INDEX, README, CLAUDE.md, risks

## Contracts added or changed
- `ModelProfile.provider | label | approved_for_student_conversations | notes`
- `OpenAIChatModel`, `foundry_chat_model`, `ollama_chat_model`; `AvailableModel(profile, model, tokens_per_minute)`
- `ChatService(..., extra_models=())`, `ChatService.models()`, `ChatService.set_model(...)`
- `Conversation.model: str | None`; `StudentChat.model`; `NewLessonChat.model`; `PATCH .../chats/{id}` accepts `model`
- `User.preferred_model`; `GET /api/models`; `PUT /api/models/preferred`

## Tests to add
`tests/model_providers/`: the adapter sends the right output-cap parameter and maps usage and errors; only approved models can be set on, or run in, a student's chat; a tutor's test chat uses their preferred model; cost and summaries use the turn's model; every registered model passes the startup check; the models API is tutor-only and shows prices; the preferred-model change is audited; an unresolved Key Vault reference counts as no key. Web: the picker's request shapes and labels.

## Open questions
- None.
