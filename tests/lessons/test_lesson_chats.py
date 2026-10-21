import pytest

from prof_ai.chat.context import LAYER_CAPS, Layer
from prof_ai.chat.models import Lesson
from prof_ai.chat.service import MAX_CHATS_PER_STUDENT
from prof_ai.lessons.rules import InvalidLessonError, lesson_tokens, render_lesson, validate_lesson
from prof_ai.users.models import Role
from tests.auth.conftest import make_user

from .conftest import RATIOS


def material_of_tokens(lesson: dict, tokens: int) -> dict:
    """The lesson with material sized so the rendered lesson is exactly this many tokens."""
    rendered = render_lesson(Lesson.model_validate({**lesson, "material": "x"}))
    other_bytes = len(rendered.encode("utf-8")) - 1
    return {**lesson, "material": "x" * (tokens * 3 - other_bytes)}


def test_lesson_at_the_cap_is_accepted_and_one_token_over_is_refused():
    cap = LAYER_CAPS[Layer.LESSON]
    at_cap = Lesson.model_validate(material_of_tokens(RATIOS, cap))
    assert lesson_tokens(validate_lesson(at_cap, licence_confirmed=True)) == cap
    over = Lesson.model_validate(material_of_tokens(RATIOS, cap + 1))
    with pytest.raises(InvalidLessonError, match="limit"):
        validate_lesson(over, licence_confirmed=True)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"title": "  "}, "title"),
        ({"title": "x" * 121}, "title"),
        ({"topics": ["t"] * 21}, "topics"),
        ({"notes": "x" * 2_001}, "notes"),
    ],
)
def test_lesson_fields_are_limited(change, message):
    with pytest.raises(InvalidLessonError, match=message):
        validate_lesson(Lesson.model_validate({**RATIOS, **change}), licence_confirmed=True)


def test_material_needs_a_licence_confirmation_but_a_plain_lesson_doesnt():
    with pytest.raises(InvalidLessonError, match="allowed"):
        validate_lesson(Lesson.model_validate(RATIOS), licence_confirmed=False)
    plain = Lesson.model_validate({**RATIOS, "material": ""})
    assert validate_lesson(plain, licence_confirmed=False).title == "Ratios"


def test_tutor_sets_up_a_lesson_chat_that_the_student_uses(h):
    response = h.create("sam", "alex", RATIOS)
    assert response.status_code == 201
    chat = response.json()
    assert (chat["title"], chat["topics"], chat["has_material"]) == (
        "Ratios",
        ["Simplifying ratios", "Sharing in a ratio"],
        True,
    )
    assert h.users.events[-1].action == "chat_created"

    listed = h.client.get("/api/chat/conversations", headers=h.as_user("alex")).json()
    assert [c["title"] for c in listed] == ["Ratios"]

    h.send("alex", chat["id"], "@AI How do I simplify 12:18?")
    system = h.model.system_prompts[-1]
    assert "Lesson material (information to teach from)" in system
    assert "Simplify by dividing by the HCF." in system
    assert "Alex mixes up the order of the parts." in system
    lesson = render_lesson(Lesson.model_validate(RATIOS))
    reply = h.store.get_conversation("alex", chat["id"]).messages[-1]
    assert reply.context.layers["lesson"] > 0
    assert lesson in system


def test_students_see_the_lesson_title_and_topics_but_never_material_or_notes(h):
    chat_id = h.create("sam", "alex", RATIOS).json()["id"]
    detail = h.client.get(f"/api/chat/conversations/{chat_id}", headers=h.as_user("alex")).json()
    assert detail["lesson"] == {
        "title": "Ratios",
        "topics": ["Simplifying ratios", "Sharing in a ratio"],
    }
    assert "HCF" not in str(detail) and "order of the parts" not in str(detail)


def test_a_title_is_kept_after_the_first_message(h):
    chat_id = h.create("sam", "alex", RATIOS).json()["id"]
    h.send("alex", chat_id, "hello there")
    assert h.store.get_conversation("alex", chat_id).title == "Ratios"


def test_students_cannot_create_chats(h):
    assert h.create("alex", "alex", RATIOS).status_code == 403
    response = h.client.post("/api/chat/conversations", headers=h.as_user("alex"))
    assert response.status_code == 403
    assert h.store.conversations == {}


def test_tutors_can_still_start_their_own_test_chat(h):
    response = h.client.post("/api/chat/conversations", headers=h.as_user("sam"))
    assert response.status_code == 201
    assert h.store.get_conversation("sam", response.json()["id"]).lesson is None


def test_a_tutor_cannot_touch_another_tutors_student(h):
    bea_chat = h.start("bea")
    assert h.create("sam", "bea", RATIOS).status_code == 404
    assert h.list("sam", "bea").status_code == 404
    assert h.delete("sam", "bea", bea_chat).status_code == 404
    assert h.store.get_conversation("bea", bea_chat) is not None


def test_unknown_students_and_other_tutors_are_404(h):
    assert h.list("sam", "nobody").status_code == 404
    assert h.create("sam", "punji", RATIOS).status_code == 404


def test_tutors_can_set_up_chats_for_themselves(h):
    assert h.create("sam", "sam", RATIOS).status_code == 201
    assert h.list("sam", "sam").json()["chats"][0]["title"] == "Ratios"


def test_admins_can_set_up_any_students_chats(h):
    h.users.save(make_user("ada", role=Role.TUTOR, email="ada@example.com"))
    h.users.save(h.users.get("ada").model_copy(update={"is_admin": True}))
    assert h.create("ada", "bea", RATIOS).status_code == 201


def test_a_student_has_at_most_five_chats_until_the_tutor_deletes_one(h):
    ids = [h.create("sam", "alex", RATIOS).json()["id"] for _ in range(MAX_CHATS_PER_STUDENT)]
    full = h.create("sam", "alex", RATIOS)
    assert full.status_code == 409
    assert "Delete one first" in full.json()["detail"]

    listing = h.list("sam", "alex").json()
    assert (len(listing["chats"]), listing["max_chats"]) == (5, 5)
    assert listing["max_lesson_tokens"] == LAYER_CAPS[Layer.LESSON]

    assert h.delete("sam", "alex", ids[0]).status_code == 204
    assert (h.users.events[-1].action, h.users.events[-1].reason) == ("chat_deleted", "Ratios")
    assert h.store.get_conversation("alex", ids[0]) is None
    assert h.create("sam", "alex", RATIOS).status_code == 201


def test_deleting_a_missing_chat_is_404(h):
    assert h.delete("sam", "alex", "nope").status_code == 404


def test_an_oversized_or_unlicensed_lesson_is_refused_and_nothing_is_saved(h):
    over = material_of_tokens(RATIOS, LAYER_CAPS[Layer.LESSON] + 1)
    response = h.create("sam", "alex", over)
    assert response.status_code == 400
    assert "limit" in response.json()["detail"]
    assert h.create("sam", "alex", RATIOS, licence=False).status_code == 400
    assert h.store.conversations == {}


def test_erasing_a_student_removes_their_lesson_chats(h):
    h.create("sam", "alex", RATIOS)
    h.service.erase_user_data("alex")
    assert h.store.list_conversations("alex") == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/students/alex/chats"),
        ("post", "/api/students/alex/chats"),
        ("delete", "/api/students/alex/chats/x"),
        ("post", "/api/lessons/extract"),
    ],
)
def test_lesson_endpoints_require_sign_in(h, method, path):
    assert h.client.request(method, path, json={}).status_code == 401
