# Handover: Model providers and a model picker

- **Owner:** punji
- **PR:** see the PR for `feat/model-providers`
- **Merged:** pending

## What was built
As planned:
- **One adapter** (`OpenAIChatModel`) for any OpenAI-compatible chat API, with factories for Foundry (managed identity, `max_completion_tokens`) and Ollama Cloud (API key, `https://ollama.com/v1`, `max_tokens`). `FoundryChatModel` is gone; use `foundry_chat_model(...)`.
- **Richer profiles:**
  - Each profile has a `provider`, `label`, `notes` and `approved_for_student_conversations` (default `False`).
  - Luna is approved.
  - New profiles `glm-5.3-flash` ($0.15 / $0.03 / $0.50 per million input / cached / output) and `deepseek-v4.1-flash` ($0.30 / $0.006 / $1.20) use Ollama's peak prices from 2026-10-21. They're registered only when `OLLAMA_API_KEY` is set.
- **A registry in `ChatService`:** the default model plus `extra_models`. Every model passes `check_budget` at startup, and Ollama skips the tokens-per-minute part.
- **Which model a turn uses:** the chat's own model, then (for a tutor's own chat) the tutor's preferred model, then the default. The turn's model is also used for its cost and its summary.
- **Approval is enforced:**
  - Setting an unapproved or unknown model on a student's chat returns 400.
  - A turn in a student's chat on an unapproved model fails closed with 503.
  - A tutor's preferred model never applies to a student's chat.
- **Lessons page:**
  - "Your default model" next to the student picker.
  - A model choice on the new-lesson form, showing the estimated cost per message and the model's notes.
  - A model dropdown on each chat row.
  - For students, unapproved models are shown but disabled.
- **Bicep:** an `OLLAMA_API_KEY` app setting as a Key Vault reference to `ollama-api-key`. Until that secret exists the reference stays unresolved, and the app treats it as no key.
- **Evals:** `prof eval dilution --model <id>` runs on any registered model.

Not built: per-model layer caps. Caps stay global and sized for Luna's 50k tokens a minute.

## How to run / use it
1. **Store the Ollama key** (asks for it without echoing; you need Key Vault Secrets Officer, which tutors have):
   ```bash
   read -s "OLLAMA_KEY?Ollama API key: " && echo && az keyvault secret set --vault-name kv-prof-ai-cjzzqh --name ollama-api-key --value "$OLLAMA_KEY" --output none && unset OLLAMA_KEY && echo "Stored."
   ```
2. **Deploy infra once** (merging deploys only the app): `bash scripts/deploy-infra.sh --what-if`, check that it only adds `OLLAMA_API_KEY`, then run it without the flag.
3. **Use it:** on the Lessons page, set "Your default model" to an Ollama model and try it in a test chat or a lesson for yourself.
- API: `GET /api/models` and `PUT /api/models/preferred` with `{"model": "<id>" | null}` (tutors only, audited as `preferred_model_changed`). `POST /api/students/{id}/chats` takes an optional `model`. `PATCH /api/students/{id}/chats/{chat_id}` takes `model` and/or `support` (model changes audited as `chat_model_changed`).
- Locally, put `OLLAMA_API_KEY` in `.env` to get the Ollama models.

## Contracts other code can rely on
- `ModelProfile.provider | label | approved_for_student_conversations | notes`; `MODEL_PROFILES` includes `GLM_FLASH` and `DEEPSEEK_FLASH` (`chat/model_profiles.py`).
- `OpenAIChatModel`, `foundry_chat_model`, `ollama_chat_model`, `OLLAMA_BASE_URL` (`chat/model.py`).
- `AvailableModel(profile, model, tokens_per_minute=None)`; `ChatService(..., extra_models=())`, `.models()`, `.default_model`, `.check_model(owner, id)`, `.set_model(owner, chat_id, id)`; `create_chat(..., model=None)` (`chat/service.py`).
- `check_budget(profile, tokens_per_minute)` accepts `None` for providers without a per-minute quota.
- `Conversation.model: str | None`; `User.preferred_model: str | None`; `StudentChat.model`.
- `Settings.ollama_api_key`; `config.secret_setting` treats an unresolved `@Microsoft.KeyVault(...)` as unset.
- `GET /api/models` → `{models: [ModelOption], default, preferred}` (`chat/models_api.py`).

## Tests added
- `tests/model_providers/`:
  - The adapter: output-cap parameter, streamed text and usage, error mapping, content filter.
  - Every registered model passes the startup check, and only Luna is approved.
  - The models API: prices, typical cost, tutors only.
  - Approval enforcement, both when a model is set and on every turn.
  - A tutor's own chat on an Ollama model, charged at its price.
  - A tutor's preferred model applies to their own chats only, and changing it is audited.
  - Changing a chat's model is audited.
  - An unresolved Key Vault reference counts as no key.
- `web/src/modelProviders.test.ts`: approved-only for students, the starting model, cost wording, and the request shapes.

## Known issues / TODOs
- The Ollama models haven't been through `prof eval dilution`, and their notes say so.
- Ollama has no content filter. Before any non-Foundry model is approved, the guard pipeline (our own Content Safety calls) has to cover it.
- In a tutor's own lesson chat, the tutor still needs `@AI` (or *Ask Prof AI*), as before.
- The suite took about 75s on this machine while other work was running (normally 10–20s).

## For the other dev
- ADR 0005 has a second **proposed** amendment: more providers, with `approved_for_student_conversations` enforced in `ChatService`. Accept it, or say what to change.
- `FoundryChatModel` was replaced by `foundry_chat_model(endpoint, deployment)`.
- Any new code that calls a model must use the turn's `AvailableModel`, not a single service-wide model.
