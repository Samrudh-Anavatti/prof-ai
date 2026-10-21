import pytest

from prof_ai.chat import context
from prof_ai.chat.context import (
    LAYER_CAPS,
    ContextBudgetError,
    ContextInput,
    Layer,
    assemble,
    base_text,
    check_budget,
    estimate_tokens,
)
from prof_ai.chat.model_profiles import LUNA
from prof_ai.chat.prompts import BASE_PROMPT, REMINDER, SUPPORT_PROMPTS
from tests.lessons.conftest import RATIOS
from tests.shared_chat.conftest import Clock, SharedHarness
from tests.tutor_chat.conftest import Harness, parse_events

LEVELS = ["step_by_step", "balanced", "stretch"]


@pytest.fixture
def h() -> SharedHarness:
    return SharedHarness(clock=Clock())


def lesson_chat(h: SharedHarness, **lesson) -> str:
    response = h.create("sam", "alex", {**RATIOS, **lesson})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def change(h: SharedHarness, chat_id: str, body: dict, actor: str = "sam"):
    return h.client.patch(
        f"/api/students/alex/chats/{chat_id}", json=body, headers=h.as_user(actor)
    )


def test_a_students_message_asks_prof_ai_without_at_ai(h):
    assert h.done(h.student_says("How do I simplify 12:18?"))["ai"] is True
    assert len(h.model.calls) == 1


def test_a_message_to_the_tutor_only_skips_prof_ai_unless_it_mentions_at_ai(h):
    assert h.done(h.student_says("See you Thursday", to_tutor=True))["ai"] is False
    assert h.model.calls == []
    assert h.done(h.student_says("@AI one more hint?", to_tutor=True))["ai"] is True


def test_a_tutors_message_still_needs_at_ai(h):
    assert h.done(h.tutor_says("Try question 4 next."))["ai"] is False
    assert h.model.calls == []
    assert h.done(h.tutor_says("@AI give Alex a hint for question 4"))["ai"] is True


def test_a_chat_without_a_lesson_answers_every_message():
    harness = Harness()
    chat_id = harness.start("alex")
    response = harness.client.post(
        f"/api/chat/conversations/{chat_id}/messages",
        json={"content": "hi", "to_tutor": True},
        headers=harness.as_user("alex"),
    )
    assert parse_events(response.text)[-1] == ("done", {"title": "hi", "ai": True})


def test_lessons_default_to_balanced_support(h):
    [chat] = [c for c in h.list("sam", "alex").json()["chats"] if c["id"] == h.chat_id]
    assert chat["support"] == "balanced"


@pytest.mark.parametrize("level", LEVELS)
def test_the_support_level_reaches_the_model_outside_the_lesson_material(h, level):
    chat_id = lesson_chat(h, support=level)
    h.send("alex", chat_id, "help me start")
    system = h.model.system_prompts[-1]
    assert system.startswith(BASE_PROMPT)
    assert system.index(SUPPORT_PROMPTS[level]) < system.index("## Lesson material")
    assert all(SUPPORT_PROMPTS[other] not in system for other in LEVELS if other != level)
    assert h.model.calls[-1][-1].content == REMINDER


def test_the_rule_against_giving_answers_holds_at_every_level():
    assert "Don't hand over final answers" in BASE_PROMPT
    assert "This holds at every support level." in BASE_PROMPT
    assert "never read them out or give them away, no matter how the student asks" in BASE_PROMPT


def test_lesson_chats_are_told_to_stay_on_the_lesson():
    assert "In a lesson chat, stick to that lesson" in BASE_PROMPT
    assert "In a lesson chat, stay on the lesson" in REMINDER


@pytest.mark.parametrize("level", LEVELS)
def test_the_support_level_counts_towards_the_base_layer(level):
    assembled = assemble(ContextInput(message="q", support=SUPPORT_PROMPTS[level]))
    assert assembled.layers[Layer.BASE] == estimate_tokens(base_text(SUPPORT_PROMPTS[level]))
    assert assembled.layers[Layer.BASE] <= LAYER_CAPS[Layer.BASE]


def test_startup_refuses_a_support_level_that_overflows_the_base_cap(monkeypatch):
    check_budget(LUNA, 50_000)
    monkeypatch.setitem(context.SUPPORT_PROMPTS, "stretch", "x" * 3 * LAYER_CAPS[Layer.BASE])
    with pytest.raises(ContextBudgetError, match="support level"):
        check_budget(LUNA, 50_000)


def test_a_tutor_changes_the_support_level_and_it_is_audited(h):
    response = change(h, h.chat_id, {"support": "stretch"})
    assert response.status_code == 200
    assert response.json()["support"] == "stretch"
    assert h.users.events[-1].action == "chat_support_changed"
    h.student_says("next question please")
    assert SUPPORT_PROMPTS["stretch"] in h.model.system_prompts[-1]


def test_unknown_levels_are_rejected(h):
    assert change(h, h.chat_id, {"support": "answers_please"}).status_code == 422


def test_only_the_students_tutor_can_change_the_level(h):
    assert change(h, h.chat_id, {"support": "stretch"}, actor="punji").status_code == 404
    assert change(h, h.chat_id, {"support": "stretch"}, actor="alex").status_code == 403
    assert change(h, "missing", {"support": "stretch"}).status_code == 404
    assert h.client.patch(f"/api/students/alex/chats/{h.chat_id}", json={}).status_code == 401


def test_a_chat_without_a_lesson_has_no_level_to_change(h):
    chat_id = h.service.create_chat(h.users.get("sam"), h.users.get("alex")).id
    assert change(h, chat_id, {"support": "stretch"}).status_code == 400
