import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from prof_ai.chat.model_profiles import ModelProfile
from prof_ai.chat.models import Author, ChatMessage, PromptMessage
from prof_ai.chat.prompts import (
    BASE_PROMPT,
    REMINDER,
    SUPPORT_PROMPTS,
    compose_system_prompt,
    support_section,
    with_references,
)


class Layer(StrEnum):
    BASE = "base"
    TEACHING_STYLE = "teaching_style"
    LESSON = "lesson"
    PROFILE = "profile"
    SUMMARY = "summary"
    HISTORY = "history"
    REFERENCE = "reference"
    MESSAGE = "message"
    REMINDER = "reminder"


LAYER_CAPS: dict[Layer, int] = {
    Layer.BASE: 2_000,
    Layer.TEACHING_STYLE: 3_000,
    Layer.LESSON: 12_000,
    Layer.PROFILE: 3_000,
    Layer.SUMMARY: 4_000,
    Layer.HISTORY: 12_000,
    Layer.REFERENCE: 4_000,
    Layer.MESSAGE: 3_000,
    Layer.REMINDER: 500,
}
OUTPUT_RESERVE = 8_000
CONTEXT_CEILING = 256_000


class ContextBudgetError(RuntimeError):
    pass


class ContextOverflowError(Exception):
    pass


def estimate_tokens(text: str) -> int:
    """Deliberately high for English (about 4 characters a token), and model-independent."""
    return math.ceil(len(text.encode("utf-8")) / 3)


def base_text(support: str | None) -> str:
    """Our own instructions: the base prompt and the lesson's support level, if any."""
    return f"{BASE_PROMPT}\n\n{support_section(support)}" if support else BASE_PROMPT


def check_budget(profile: ModelProfile, tokens_per_minute: int | None) -> None:
    """tokens_per_minute is None for providers without a per-minute token quota."""
    largest_base = max(estimate_tokens(base_text(s)) for s in SUPPORT_PROMPTS.values())
    if largest_base > LAYER_CAPS[Layer.BASE]:
        raise ContextBudgetError(
            f"The base prompt with a support level is {largest_base} tokens, over its "
            f"{LAYER_CAPS[Layer.BASE]} cap."
        )
    largest_request = sum(LAYER_CAPS.values()) + profile.max_output_tokens
    if tokens_per_minute is not None and largest_request > tokens_per_minute:
        raise ContextBudgetError(
            f"A full turn can reach {largest_request} tokens, over the deployment's "
            f"{tokens_per_minute} tokens a minute, so it would never be accepted."
        )
    budget = sum(LAYER_CAPS.values()) + OUTPUT_RESERVE
    if budget > CONTEXT_CEILING:
        raise ContextBudgetError(f"Layer caps total {budget}, over the {CONTEXT_CEILING} ceiling.")
    if CONTEXT_CEILING > profile.context_window:
        raise ContextBudgetError(
            f"{profile.deployment} has a {profile.context_window}-token window, "
            f"smaller than the {CONTEXT_CEILING} ceiling."
        )
    if profile.max_output_tokens > OUTPUT_RESERVE:
        raise ContextBudgetError(
            f"{profile.deployment} allows {profile.max_output_tokens} output tokens, "
            f"over the {OUTPUT_RESERVE} reserve."
        )


def history_window_start(
    messages: Sequence[ChatMessage], cap: int = LAYER_CAPS[Layer.HISTORY]
) -> int:
    """Index of the oldest message in the newest run that fits the history cap."""
    used = 0
    start = len(messages)
    for index in range(len(messages) - 1, -1, -1):
        used += estimate_tokens(messages[index].content)
        if used > cap:
            break
        start = index
    return start


def fit_references(references: Sequence[str], cap: int = LAYER_CAPS[Layer.REFERENCE]) -> list[str]:
    """Whole snippets, best first, until the reference cap is full."""
    kept: list[str] = []
    used = 0
    for snippet in references:
        used += estimate_tokens(snippet)
        if used > cap:
            break
        kept.append(snippet)
    return kept


# Removed from message text so nobody can type a label that looks like the system's (R25).
LABEL_MARKS = str.maketrans("", "", "⟦⟧")


def speaker_label(author: Author, name: str | None) -> str:
    role = "Tutor" if author == "tutor" else "Student"
    name = (name or "").translate(LABEL_MARKS).strip()
    return f"⟦{role} {name}⟧" if name else f"⟦{role}⟧"


def labelled(content: str, author: Author, name: str | None) -> str:
    """A human message as the model sees it: a label it can trust, then the text."""
    return f"{speaker_label(author, name)} {content.translate(LABEL_MARKS)}"


@dataclass(frozen=True)
class ContextInput:
    message: str
    message_author: Author = "student"
    message_author_name: str | None = None
    # Older messages have no author: they were written by the chat's owner.
    owner_author: Author = "student"
    owner_name: str | None = None
    teaching_style: str | None = None
    support: str | None = None
    lesson: str | None = None
    profile: str | None = None
    summary: str | None = None
    history: Sequence[ChatMessage] = ()
    references: Sequence[str] = ()


def history_text(message: ChatMessage, context: ContextInput) -> str:
    if message.role == "assistant":
        return message.content
    if message.author is None:
        return labelled(message.content, context.owner_author, context.owner_name)
    return labelled(message.content, message.author, message.author_name)


@dataclass(frozen=True)
class AssembledContext:
    messages: list[PromptMessage]
    layers: dict[str, int]

    @property
    def estimated_input(self) -> int:
        return sum(self.layers.values())


def assemble(context: ContextInput, caps: Mapping[Layer, int] = LAYER_CAPS) -> AssembledContext:
    """Build one model call from capped layers, ordered so the stable prefix can be cached.

    Only evals pass other caps, to measure sizes beyond what the app allows.
    """
    fixed = {
        Layer.BASE: base_text(context.support),
        Layer.TEACHING_STYLE: context.teaching_style or "",
        Layer.LESSON: context.lesson or "",
        Layer.PROFILE: context.profile or "",
        Layer.SUMMARY: context.summary or "",
        Layer.MESSAGE: context.message,
        Layer.REMINDER: REMINDER,
    }
    sizes = {layer: estimate_tokens(text) for layer, text in fixed.items()}
    over = [layer.value for layer, size in sizes.items() if size > caps[layer]]
    if over:
        raise ContextOverflowError(f"Context layers over their caps: {', '.join(over)}.")

    history = context.history[history_window_start(context.history, caps[Layer.HISTORY]) :]
    references = fit_references(context.references, caps[Layer.REFERENCE])
    sizes[Layer.HISTORY] = sum(estimate_tokens(m.content) for m in history)
    sizes[Layer.REFERENCE] = sum(estimate_tokens(r) for r in references)

    system = compose_system_prompt(
        teaching_style=context.teaching_style,
        support=context.support,
        lesson=context.lesson,
        profile=context.profile,
        summary=context.summary,
    )
    message = labelled(context.message, context.message_author, context.message_author_name)
    messages = [
        PromptMessage(role="system", content=system),
        *(PromptMessage(role=m.role, content=history_text(m, context)) for m in history),
        PromptMessage(role="user", content=with_references(message, references)),
        PromptMessage(role="system", content=REMINDER),
    ]
    return AssembledContext(messages, {layer.value: sizes[layer] for layer in Layer})
