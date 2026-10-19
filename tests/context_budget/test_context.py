from dataclasses import replace

import pytest

from prof_ai.chat.context import (
    CONTEXT_CEILING,
    LAYER_CAPS,
    OUTPUT_RESERVE,
    ContextBudgetError,
    ContextInput,
    ContextOverflowError,
    Layer,
    assemble,
    check_budget,
    estimate_tokens,
)
from prof_ai.chat.model_profiles import LUNA, UnknownModelError, model_profile
from prof_ai.chat.models import ChatMessage, Usage
from prof_ai.chat.prompts import BASE_PROMPT, REMINDER
from tests.tutor_chat.conftest import FIXED_NOW


def message(role: str, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content, at=FIXED_NOW)


def sized(tokens: int, fill: str = "x") -> str:
    """Text that estimates to exactly this many tokens."""
    return fill * (tokens * 3)


def test_default_caps_fit_the_ceiling_and_lunas_window():
    assert sum(LAYER_CAPS.values()) + OUTPUT_RESERVE <= CONTEXT_CEILING
    assert LAYER_CAPS[Layer.LESSON] == 64_000
    assert LAYER_CAPS[Layer.REFERENCE] == 64_000
    check_budget(LUNA)


def test_a_model_with_a_smaller_window_is_refused():
    with pytest.raises(ContextBudgetError):
        check_budget(replace(LUNA, context_window=128_000))


def test_a_model_allowed_more_output_than_the_reserve_is_refused():
    with pytest.raises(ContextBudgetError):
        check_budget(replace(LUNA, max_output_tokens=OUTPUT_RESERVE + 1))


def test_unknown_deployment_has_no_profile():
    assert model_profile("gpt-5.6-luna") is LUNA
    with pytest.raises(UnknownModelError):
        model_profile("some-other-model")


def test_token_estimate_counts_bytes_so_it_runs_high():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2
    assert estimate_tokens("é" * 3) == 2


def test_cost_counts_cached_input_at_the_cached_price():
    usage = Usage(input_tokens=1_000_000, cached_input_tokens=500_000, output_tokens=100_000)
    assert LUNA.cost_micro_usd(usage) == 500_000 * 0.20 + 500_000 * 0.02 + 100_000 * 1.20


def test_layers_are_ordered_most_stable_first_with_the_reminder_last():
    assembled = assemble(
        ContextInput(
            message="What's a ratio?",
            teaching_style="STYLE",
            lesson="LESSON",
            profile="PROFILE",
            summary="SUMMARY",
            history=[message("user", "earlier"), message("assistant", "reply")],
            references=["REFERENCE"],
        )
    )
    system, *middle, user, reminder = assembled.messages
    assert system.role == "system" and system.content.startswith(BASE_PROMPT)
    positions = [system.content.index(t) for t in ("STYLE", "LESSON", "PROFILE", "SUMMARY")]
    assert positions == sorted(positions)
    assert [(m.role, m.content) for m in middle] == [("user", "earlier"), ("assistant", "reply")]
    assert user.role == "user"
    assert user.content.index("REFERENCE") < user.content.index("What's a ratio?")
    assert "information to teach from" in user.content
    assert (reminder.role, reminder.content) == ("system", REMINDER)


def test_message_without_references_is_sent_as_typed():
    assembled = assemble(ContextInput(message="hi"))
    assert assembled.messages[-2].content == "hi"
    assert assembled.layers[Layer.REFERENCE] == 0


def test_the_prefix_is_identical_from_one_turn_to_the_next():
    first_history = [message("user", "q1"), message("assistant", "a1")]
    common = {"teaching_style": "STYLE", "profile": "PROFILE", "summary": "SUMMARY"}
    first = assemble(ContextInput(message="q2", history=first_history, **common))
    second = assemble(
        ContextInput(
            message="q3",
            history=[*first_history, message("user", "q2"), message("assistant", "a2")],
            references=["only for this turn"],
            **common,
        )
    )
    shared = len(first_history) + 1
    assert first.messages[:shared] == second.messages[:shared]


def test_history_keeps_the_newest_messages_that_fit():
    history = [message("user", f"{i:02d}" + sized(2_000)[2:]) for i in range(40)]
    assembled = assemble(ContextInput(message="now", history=history))
    sent = assembled.messages[1:-2]
    assert len(sent) == LAYER_CAPS[Layer.HISTORY] // 2_000
    assert sent[-1].content.startswith("39")
    assert assembled.layers[Layer.HISTORY] <= LAYER_CAPS[Layer.HISTORY]


def test_an_oversized_old_message_cuts_the_window_there():
    history = [
        message("user", "oldest"),
        message("assistant", sized(LAYER_CAPS[Layer.HISTORY] + 1)),
        message("user", "recent question"),
        message("assistant", "recent answer"),
    ]
    sent = assemble(ContextInput(message="now", history=history)).messages[1:-2]
    assert [m.content for m in sent] == ["recent question", "recent answer"]


def test_references_beyond_the_cap_drop_lowest_ranked_first():
    best, second, third = sized(30_000, "a"), sized(30_000, "b"), sized(30_000, "c")
    assembled = assemble(ContextInput(message="q", references=[best, second, third]))
    user = assembled.messages[-2].content
    assert best in user and second in user and third not in user
    assert assembled.layers[Layer.REFERENCE] == 60_000


@pytest.mark.parametrize(
    "layer",
    ["teaching_style", "lesson", "profile", "summary", "message"],
)
def test_a_fixed_layer_over_its_cap_is_refused(layer):
    cap = LAYER_CAPS[Layer(layer)]
    with pytest.raises(ContextOverflowError, match=layer):
        assemble(ContextInput(**{"message": "q", layer: sized(cap + 1)}))


def test_ledger_has_every_layer():
    assembled = assemble(ContextInput(message="q", profile="PROFILE"))
    assert list(assembled.layers) == [layer.value for layer in Layer]
    assert assembled.layers[Layer.BASE] == estimate_tokens(BASE_PROMPT)
    assert assembled.estimated_input == sum(assembled.layers.values())
