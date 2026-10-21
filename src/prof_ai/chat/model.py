from collections.abc import Iterator, Sequence
from typing import Protocol

from prof_ai.chat.models import PromptMessage, Usage


class ContentFilteredError(Exception):
    pass


class ModelUnavailableError(Exception):
    pass


class ModelRateLimitedError(ModelUnavailableError):
    """The deployment's tokens- or requests-per-minute quota is used up."""


class ChatModel(Protocol):
    def stream(
        self, messages: Sequence[PromptMessage], max_output_tokens: int
    ) -> Iterator[str | Usage]:
        """Yield reply text deltas, then one Usage."""
        ...


OLLAMA_BASE_URL = "https://ollama.com/v1"


class OpenAIChatModel:
    """Any provider with an OpenAI-compatible chat completions API."""

    def __init__(self, client, model: str, output_cap_param: str):
        self._client = client
        self._model = model
        # Foundry's v1 API takes max_completion_tokens; Ollama's takes max_tokens.
        self._output_cap_param = output_cap_param

    def stream(
        self, messages: Sequence[PromptMessage], max_output_tokens: int
    ) -> Iterator[str | Usage]:
        import openai

        try:
            chunks = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                stream=True,
                stream_options={"include_usage": True},
                reasoning_effort="low",
                **{self._output_cap_param: max_output_tokens},
            )
            for chunk in chunks:
                for choice in chunk.choices:
                    if choice.delta.content:
                        yield choice.delta.content
                    if choice.finish_reason == "content_filter":
                        raise ContentFilteredError()
                if chunk.usage:
                    details = chunk.usage.prompt_tokens_details
                    yield Usage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                        cached_input_tokens=(details.cached_tokens or 0) if details else 0,
                    )
        except openai.BadRequestError as error:
            if error.code == "content_filter":
                raise ContentFilteredError() from error
            raise ModelUnavailableError() from error
        except openai.RateLimitError as error:
            raise ModelRateLimitedError() from error
        except openai.OpenAIError as error:
            raise ModelUnavailableError() from error


def foundry_chat_model(endpoint: str, deployment: str) -> OpenAIChatModel:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = OpenAI(
        base_url=f"{endpoint.rstrip('/')}/openai/v1/",
        api_key=token_provider,
        timeout=60,
        max_retries=1,
    )
    return OpenAIChatModel(client, deployment, "max_completion_tokens")


def ollama_chat_model(api_key: str, model: str, base_url: str = OLLAMA_BASE_URL) -> OpenAIChatModel:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=60, max_retries=1)
    return OpenAIChatModel(client, model, "max_tokens")
