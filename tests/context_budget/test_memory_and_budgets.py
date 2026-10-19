from collections.abc import Iterator, Sequence

import pytest

from prof_ai.chat.context import LAYER_CAPS, Layer
from prof_ai.chat.memory import SUMMARY_OUTPUT_TOKENS
from prof_ai.chat.model_profiles import LUNA
from prof_ai.chat.models import ChatMessage, PromptMessage, Usage
from prof_ai.chat.prompts import SUMMARISE_PROMPT
from prof_ai.chat.service import UNAVAILABLE, ChatLimits
from prof_ai.cli import TutorTools, main
from tests.tutor_chat.conftest import FIXED_NOW, FakeModel, Harness, parse_events

TODAY = FIXED_NOW.date()
SUMMARY_TEXT = "- Covered ratios.\n- Finds simplifying hard."
TURN_COST = LUNA.cost_micro_usd(Usage(input_tokens=120, output_tokens=30))


class ScriptedModel(FakeModel):
    """Answers summary requests differently from chat turns."""

    def __init__(self) -> None:
        super().__init__()
        self.summary_error: Exception | None = None

    def stream(
        self, messages: Sequence[PromptMessage], max_output_tokens: int
    ) -> Iterator[str | Usage]:
        if messages[0].content != SUMMARISE_PROMPT:
            yield from super().stream(messages, max_output_tokens)
            return
        self.calls.append(list(messages))
        self.output_caps.append(max_output_tokens)
        if self.summary_error:
            raise self.summary_error
        yield SUMMARY_TEXT
        yield self.usage


@pytest.fixture
def h() -> Harness:
    return Harness(model=ScriptedModel())


def long_chat(h: Harness, user_id: str = "alex", count: int = 40, summary: str = "") -> str:
    """A saved conversation of messages that each estimate to 2,000 tokens."""
    conversation_id = h.start(user_id)
    conversation = h.store.get_conversation(user_id, conversation_id)
    conversation.messages = [
        ChatMessage(
            role="user" if i % 2 == 0 else "assistant",
            content=f"{i:02d}" + "x" * 5_998,
            at=FIXED_NOW,
        )
        for i in range(count)
    ]
    conversation.summary = summary
    h.store.save_conversation(conversation)
    return conversation_id


def summary_calls(h: Harness) -> list[list[PromptMessage]]:
    return [call for call in h.model.calls if call[0].content == SUMMARISE_PROMPT]


def test_short_chats_are_not_summarised(h):
    conversation_id = h.start("alex")
    for turn in range(5):
        h.send("alex", conversation_id, f"question {turn}")
    assert summary_calls(h) == []
    assert h.store.get_conversation("alex", conversation_id).summary == ""


def test_messages_that_fall_out_of_the_window_are_summarised(h):
    conversation_id = long_chat(h)
    events = parse_events(h.send("alex", conversation_id, "next question").text)
    assert events[-1][0] == "done"

    [request] = summary_calls(h)
    assert "00" + "x" * 10 in request[1].content
    assert h.model.output_caps[-1] == SUMMARY_OUTPUT_TOKENS
    stored = h.store.get_conversation("alex", conversation_id)
    assert stored.summary == SUMMARY_TEXT
    assert stored.summarised_count == 6
    assert len(stored.messages) == 42


def test_the_summary_is_sent_with_later_turns_and_folded_into_the_next_one(h):
    conversation_id = long_chat(h, summary="- Earlier: fractions.")
    h.send("alex", conversation_id, "next question")
    [request] = summary_calls(h)
    assert "- Earlier: fractions." in request[1].content

    h.send("alex", conversation_id, "and another")
    chat_turns = [c for c in h.model.calls if c[0].content != SUMMARISE_PROMPT]
    assert SUMMARY_TEXT in chat_turns[-1][0].content


def test_a_failed_summary_keeps_the_turn_and_is_retried(h):
    conversation_id = long_chat(h)
    h.model.summary_error = ConnectionError("Foundry down")
    events = parse_events(h.send("alex", conversation_id, "next question").text)
    assert events[-1][0] == "done"
    stored = h.store.get_conversation("alex", conversation_id)
    assert (stored.summary, stored.summarised_count, len(stored.messages)) == ("", 0, 42)

    h.model.summary_error = None
    h.send("alex", conversation_id, "again")
    assert h.store.get_conversation("alex", conversation_id).summary == SUMMARY_TEXT
    assert len(summary_calls(h)) == 2


def test_summary_calls_are_charged_to_the_sender(h):
    h.send("alex", long_chat(h), "next question")
    assert h.store.cost_used("alex", TODAY) == 2 * TURN_COST


def test_a_corrupt_oversized_layer_refuses_the_turn_before_the_model():
    h = Harness()
    conversation_id = h.start("alex")
    conversation = h.store.get_conversation("alex", conversation_id)
    conversation.summary = "x" * (LAYER_CAPS[Layer.SUMMARY] * 3 + 3)
    h.store.save_conversation(conversation)

    response = h.send("alex", conversation_id, "hi")
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE
    assert h.model.calls == []
    assert h.store.get_conversation("alex", conversation_id).messages == []
    assert h.send("alex", h.start("alex"), "fresh chat").status_code == 200


def test_each_reply_records_what_the_model_was_sent_and_what_it_cost():
    h = Harness()
    conversation_id = h.start("alex")
    h.send("alex", conversation_id, "hi")
    reply = h.store.get_conversation("alex", conversation_id).messages[-1]
    assert reply.context is not None
    assert set(reply.context.layers) == {layer.value for layer in Layer}
    assert reply.context.layers["message"] == 1
    assert reply.context.estimated_input == sum(reply.context.layers.values())
    assert (reply.context.input_tokens, reply.context.output_tokens) == (120, 30)
    assert reply.context.cost_micro_usd == TURN_COST
    assert h.model.output_caps == [LUNA.max_output_tokens]


def test_the_ledger_and_summary_are_not_sent_to_the_browser(h):
    conversation_id = long_chat(h)
    h.send("alex", conversation_id, "next question")
    detail = h.client.get(
        f"/api/chat/conversations/{conversation_id}", headers=h.as_user("alex")
    ).json()
    assert set(detail) == {"id", "title", "updated_at", "lesson", "messages"}
    assert all(set(m) == {"role", "content", "at"} for m in detail["messages"])


def test_tutors_are_not_held_to_the_student_budget():
    h = Harness()
    h.store.add_usage("sam", TODAY, 0, round((h.limits.daily_user_usd + 0.1) * 1_000_000))
    assert h.send("sam", h.start("sam"), "testing my style").status_code == 200
    h.store.add_usage("alex", TODAY, 0, round(h.limits.daily_user_usd * 1_000_000))
    assert h.send("alex", h.start("alex"), "one more").status_code == 429


def test_tutor_spend_counts_towards_the_global_cap():
    h = Harness(ChatLimits(daily_user_usd=1.0, daily_global_usd=0.001))
    conversation_id = h.start("sam")
    for _ in range(int(1_000 / TURN_COST) + 1):
        h.send("sam", conversation_id, "hi")
    response = h.send("alex", h.start("alex"), "hi")
    assert response.status_code == 503
    assert h.store.cost_used("alex", TODAY) == 0


def test_deleting_a_users_data_removes_their_summaries(h):
    long_chat(h, "bea")
    h.service.erase_user_data("bea")
    assert h.store.list_conversations("bea") == []


def test_cli_shows_the_summary_and_context_sizes(h, capsys):
    conversation_id = long_chat(h)
    h.send("alex", conversation_id, "next question")
    tools = TutorTools(h.users, h.profiles, h.store)
    code = main(["chats", "show", "alex@example.com", conversation_id], tools_factory=lambda: tools)
    out, _ = capsys.readouterr()
    assert code == 0
    assert f"--- summary of the first 6 messages ---\n{SUMMARY_TEXT}" in out
    assert "context: estimated" in out
    assert "reported 120 in (0 cached), 30 out" in out
