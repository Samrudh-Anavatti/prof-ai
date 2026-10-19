import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from prof_ai.chat.model_profiles import ModelProfile
from prof_ai.chat.models import ChatMessage, PromptMessage
from prof_ai.chat.prompts import BASE_PROMPT, REMINDER, compose_system_prompt, with_references


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
    Layer.LESSON: 64_000,
    Layer.PROFILE: 3_000,
    Layer.SUMMARY: 4_000,
    Layer.HISTORY: 32_000,
    Layer.REFERENCE: 64_000,
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


def check_budget(profile: ModelProfile) -> None:
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


def history_window_start(messages: Sequence[ChatMessage]) -> int:
    """Index of the oldest message in the newest run that fits the history cap."""
    used = 0
    start = len(messages)
    for index in range(len(messages) - 1, -1, -1):
        used += estimate_tokens(messages[index].content)
        if used > LAYER_CAPS[Layer.HISTORY]:
            break
        start = index
    return start


def fit_references(references: Sequence[str]) -> list[str]:
    """Whole snippets, best first, until the reference cap is full."""
    kept: list[str] = []
    used = 0
    for snippet in references:
        used += estimate_tokens(snippet)
        if used > LAYER_CAPS[Layer.REFERENCE]:
            break
        kept.append(snippet)
    return kept


@dataclass(frozen=True)
class ContextInput:
    message: str
    teaching_style: str | None = None
    lesson: str | None = None
    profile: str | None = None
    summary: str | None = None
    history: Sequence[ChatMessage] = ()
    references: Sequence[str] = ()


@dataclass(frozen=True)
class AssembledContext:
    messages: list[PromptMessage]
    layers: dict[str, int]

    @property
    def estimated_input(self) -> int:
        return sum(self.layers.values())


def assemble(context: ContextInput) -> AssembledContext:
    """Build one model call from capped layers, ordered so the stable prefix can be cached."""
    fixed = {
        Layer.BASE: BASE_PROMPT,
        Layer.TEACHING_STYLE: context.teaching_style or "",
        Layer.LESSON: context.lesson or "",
        Layer.PROFILE: context.profile or "",
        Layer.SUMMARY: context.summary or "",
        Layer.MESSAGE: context.message,
        Layer.REMINDER: REMINDER,
    }
    sizes = {layer: estimate_tokens(text) for layer, text in fixed.items()}
    over = [layer.value for layer, size in sizes.items() if size > LAYER_CAPS[layer]]
    if over:
        raise ContextOverflowError(f"Context layers over their caps: {', '.join(over)}.")

    history = context.history[history_window_start(context.history) :]
    references = fit_references(context.references)
    sizes[Layer.HISTORY] = sum(estimate_tokens(m.content) for m in history)
    sizes[Layer.REFERENCE] = sum(estimate_tokens(r) for r in references)

    system = compose_system_prompt(
        teaching_style=context.teaching_style,
        lesson=context.lesson,
        profile=context.profile,
        summary=context.summary,
    )
    messages = [
        PromptMessage(role="system", content=system),
        *(PromptMessage(role=m.role, content=m.content) for m in history),
        PromptMessage(role="user", content=with_references(context.message, references)),
        PromptMessage(role="system", content=REMINDER),
    ]
    return AssembledContext(messages, {layer.value: sizes[layer] for layer in Layer})
