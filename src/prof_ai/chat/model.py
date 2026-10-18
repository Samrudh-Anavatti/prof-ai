from collections.abc import Iterator, Sequence
from typing import Protocol

from prof_ai.chat.models import ChatMessage, Usage

MAX_OUTPUT_TOKENS = 1000


class ContentFilteredError(Exception):
    pass


class ModelUnavailableError(Exception):
    pass


class ChatModel(Protocol):
    def stream(self, system_prompt: str, messages: Sequence[ChatMessage]) -> Iterator[str | Usage]:
        """Yield reply text deltas, then one Usage."""
        ...


class FoundryChatModel:
    def __init__(self, endpoint: str, deployment: str):
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import OpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        self._client = OpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=token_provider,
            timeout=60,
            max_retries=1,
        )
        self._deployment = deployment

    def stream(self, system_prompt: str, messages: Sequence[ChatMessage]) -> Iterator[str | Usage]:
        import openai

        try:
            chunks = self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *({"role": m.role, "content": m.content} for m in messages),
                ],
                stream=True,
                stream_options={"include_usage": True},
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                reasoning_effort="low",
            )
            for chunk in chunks:
                for choice in chunk.choices:
                    if choice.delta.content:
                        yield choice.delta.content
                    if choice.finish_reason == "content_filter":
                        raise ContentFilteredError()
                if chunk.usage:
                    yield Usage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                    )
        except openai.BadRequestError as error:
            if error.code == "content_filter":
                raise ContentFilteredError() from error
            raise ModelUnavailableError() from error
        except openai.OpenAIError as error:
            raise ModelUnavailableError() from error
