from collections.abc import Sequence

from prof_ai.chat.context import LAYER_CAPS, Layer, estimate_tokens, history_window_start
from prof_ai.chat.models import ChatMessage, Conversation, PromptMessage
from prof_ai.chat.prompts import SUMMARISE_PROMPT

SUMMARY_TRIGGER_TOKENS = 8_000
SUMMARY_BATCH_TOKENS = 12_000
SUMMARY_OUTPUT_TOKENS = 1_500
MAX_SUMMARY_BYTES = LAYER_CAPS[Layer.SUMMARY] * 3


def messages_to_summarise(conversation: Conversation) -> list[ChatMessage]:
    """The oldest unsummarised messages outside the history window, once there are enough."""
    window_start = history_window_start(conversation.messages)
    pending = conversation.messages[conversation.summarised_count : window_start]
    if sum(estimate_tokens(m.content) for m in pending) < SUMMARY_TRIGGER_TOKENS:
        return []
    batch: list[ChatMessage] = []
    used = 0
    for message in pending:
        used += estimate_tokens(message.content)
        if batch and used > SUMMARY_BATCH_TOKENS:
            break
        batch.append(message)
    return batch


def speaker(message: ChatMessage) -> str:
    if message.role == "assistant":
        return "Prof AI"
    role = "Tutor" if message.author == "tutor" else "Student"
    return f"{role} {message.author_name}" if message.author_name else role


def summary_request(previous: str, messages: Sequence[ChatMessage]) -> list[PromptMessage]:
    transcript = "\n\n".join(f"{speaker(m)}: {m.content}" for m in messages)
    return [
        PromptMessage(role="system", content=SUMMARISE_PROMPT),
        PromptMessage(
            role="user",
            content=f"## Notes so far\n\n{previous or '(none yet)'}\n\n"
            f"## Next part of the conversation\n\n{transcript}",
        ),
    ]


def clip_summary(text: str) -> str:
    return text.strip().encode("utf-8")[:MAX_SUMMARY_BYTES].decode("utf-8", "ignore").strip()
