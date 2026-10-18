from datetime import date

import pytest

from prof_ai.chat.limits import TurnLimiter
from prof_ai.chat.model import ContentFilteredError
from prof_ai.chat.service import (
    FILTERED,
    HISTORY_MESSAGES,
    MAX_INPUT_CHARS,
    UNAVAILABLE,
    ChatLimits,
)
from prof_ai.profiles.store import ProfileFile

from .conftest import FIXED_NOW, Harness, parse_events

TODAY = FIXED_NOW.date()


def test_reply_streams_as_server_sent_events(harness):
    conversation_id = harness.start("alex")
    response = harness.send("alex", conversation_id, "How do I factorise x^2 + 5x + 6?")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response.text)
    assert [kind for kind, _ in events] == ["delta", "delta", "delta", "done"]
    assert "".join(data["text"] for kind, data in events if kind == "delta") == (
        "Good question! What do you know already?"
    )
    assert events[-1][1] == {"title": "How do I factorise x^2 + 5x + 6?"}


def test_turn_is_saved_with_usage(harness):
    conversation_id = harness.start("alex")
    harness.send("alex", conversation_id, "Help with fractions")
    detail = harness.client.get(
        f"/api/chat/conversations/{conversation_id}", headers=harness.as_user("alex")
    ).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "Help with fractions"
    assert detail["title"] == "Help with fractions"
    assert harness.store.tokens_used("alex", TODAY) == 150


def test_model_gets_the_users_own_system_prompt(harness):
    harness.profiles.put("sam", ProfileFile.TEACHING_STYLE, "Sam style.")
    harness.profiles.put("punjy", ProfileFile.TEACHING_STYLE, "Punjy style.")
    harness.send("alex", harness.start("alex"), "hi")
    harness.send("bea", harness.start("bea"), "hi")
    (alex_prompt, _), (bea_prompt, _) = harness.model.calls
    assert "Sam style." in alex_prompt and "Punjy style." not in alex_prompt
    assert "Punjy style." in bea_prompt and "Sam style." not in bea_prompt


def test_conversations_are_private_to_their_owner(harness):
    conversation_id = harness.start("alex")
    harness.send("alex", conversation_id, "my secret question")
    bea = harness.as_user("bea")
    assert harness.client.get("/api/chat/conversations", headers=bea).json() == []
    assert (
        harness.client.get(f"/api/chat/conversations/{conversation_id}", headers=bea).status_code
        == 404
    )
    assert harness.send("bea", conversation_id, "hijack").status_code == 404
    assert len(harness.model.calls) == 1


def test_conversation_list_shows_only_summaries(harness):
    conversation_id = harness.start("alex")
    harness.send("alex", conversation_id, "Photosynthesis")
    listed = harness.client.get("/api/chat/conversations", headers=harness.as_user("alex")).json()
    assert listed == [
        {"id": conversation_id, "title": "Photosynthesis", "updated_at": "2026-10-18T09:00:00Z"}
    ]


def test_history_sent_to_the_model_is_truncated(harness):
    conversation_id = harness.start("alex")
    for turn in range(15):
        harness.send("alex", conversation_id, f"question {turn}")
    _, messages = harness.model.calls[-1]
    assert len(messages) == HISTORY_MESSAGES
    assert messages[-1].content == "question 14"


@pytest.mark.parametrize("content", ["", "   ", "x" * (MAX_INPUT_CHARS + 1)])
def test_empty_or_long_messages_are_refused_before_the_model(harness, content):
    response = harness.send("alex", harness.start("alex"), content)
    assert response.status_code == 400
    assert harness.model.calls == []


def test_daily_user_budget_stops_chat(harness):
    conversation_id = harness.start("alex")
    harness.store.add_tokens("alex", TODAY, harness.limits.daily_user_tokens)
    response = harness.send("alex", conversation_id, "one more?")
    assert response.status_code == 429
    assert "allowance" in response.json()["detail"]
    assert harness.model.calls == []
    assert harness.send("bea", harness.start("bea"), "hi").status_code == 200


def test_yesterdays_usage_doesnt_count(harness):
    harness.store.add_tokens("alex", date(2026, 10, 17), harness.limits.daily_user_tokens)
    assert harness.send("alex", harness.start("alex"), "hi").status_code == 200


def test_global_daily_cap_stops_everyone():
    harness = Harness(ChatLimits(daily_user_tokens=1000, daily_global_tokens=1000))
    harness.store.add_tokens("bea", TODAY, 1000)
    response = harness.send("alex", harness.start("alex"), "hi")
    assert response.status_code == 503
    assert harness.model.calls == []


def test_kill_switch_stops_chat():
    harness = Harness(ChatLimits(enabled=False))
    response = harness.send("alex", harness.start("alex"), "hi")
    assert response.status_code == 503
    assert harness.model.calls == []


def test_rate_limit_and_single_reply_in_flight():
    limiter = TurnLimiter(per_minute=2, clock=lambda: 0.0)
    assert limiter.try_acquire("alex") is None
    assert "current reply" in limiter.try_acquire("alex")
    limiter.release("alex")
    assert limiter.try_acquire("alex") is None
    limiter.release("alex")
    assert "too quickly" in limiter.try_acquire("alex")
    assert limiter.try_acquire("bea") is None


def test_stuck_in_flight_turn_expires():
    now = [0.0]
    limiter = TurnLimiter(clock=lambda: now[0])
    limiter.try_acquire("alex")
    now[0] = 121.0
    assert limiter.try_acquire("alex") is None


def test_content_filter_hit_is_flagged_and_reply_withheld(harness):
    conversation_id = harness.start("alex")
    harness.model.error = ContentFilteredError()
    events = parse_events(harness.send("alex", conversation_id, "something nasty").text)
    assert events[-1] == ("error", {"message": FILTERED})
    stored = harness.store.get_conversation("alex", conversation_id)
    assert stored.messages == []
    assert [(f.kind, f.message) for f in stored.flags] == [("content_filter", "something nasty")]


def test_model_failure_saves_nothing(harness):
    conversation_id = harness.start("alex")
    harness.model.error = ConnectionError("Foundry down")
    events = parse_events(harness.send("alex", conversation_id, "hello").text)
    assert events[-1] == ("error", {"message": UNAVAILABLE})
    assert harness.store.get_conversation("alex", conversation_id).messages == []
    assert harness.store.tokens_used("alex", TODAY) == 0


def test_store_failure_after_reply_reports_an_error(harness):
    conversation_id = harness.start("alex")
    harness.store.fail_saves = True
    events = parse_events(harness.send("alex", conversation_id, "hello").text)
    assert events[-1] == ("error", {"message": UNAVAILABLE})


def test_failed_turn_frees_the_user_for_the_next_message(harness):
    conversation_id = harness.start("alex")
    harness.model.error = ConnectionError("Foundry down")
    harness.send("alex", conversation_id, "hello")
    harness.model.error = None
    assert parse_events(harness.send("alex", conversation_id, "again").text)[-1][0] == "done"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/chat/conversations"),
        ("post", "/api/chat/conversations"),
        ("get", "/api/chat/conversations/x"),
        ("post", "/api/chat/conversations/x/messages"),
    ],
)
def test_chat_endpoints_require_sign_in(harness, method, path):
    assert harness.client.request(method, path, json={"content": "hi"}).status_code == 401


def test_locked_account_cannot_chat(harness):
    conversation_id = harness.start("alex")
    alex = harness.users.get("alex")
    harness.users.save(alex.model_copy(update={"status": "account_locked"}))
    assert harness.send("alex", conversation_id, "hi").status_code == 403
    assert harness.model.calls == []
