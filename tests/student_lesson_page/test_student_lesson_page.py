import json

import pytest

from prof_ai.chat.checking import (
    CHECK_OUTPUT_TOKENS,
    NO_KEY,
    NOT_YET,
    leaks_key,
    matches_key,
)
from prof_ai.chat.model_profiles import LUNA
from prof_ai.chat.service import ChatLimits
from tests.lessons.conftest import RATIOS, LessonHarness
from tests.tutor_chat.conftest import FIXED_NOW

QUESTIONS = [
    {"number": "A1.1", "text": "Solve $x + y = 11$, $x - y = 3$.", "answer": "$x=7$, $y=4$"},
    {"number": "A1.2", "text": "Solve $2x + y = 13$, $x + y = 8$.", "answer": "$x = 5$, $y = 3$"},
    {"number": "A2.5", "text": "Two numbers sum to 26 and differ by 8.", "answer": None},
]
WORKSHEET = {
    **RATIOS,
    "material": "",
    "support": "step_by_step",
    "worked_examples": [{"title": "Elimination", "text": "Subtract to remove $y$."}],
    "questions": QUESTIONS,
}
KEY = "x=7$, $y=4"


class LessonPageHarness(LessonHarness):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.chat_id = self.create("sam", "alex", WORKSHEET).json()["id"]

    def ask(self, content: str, question: str | None = None, user: str = "alex"):
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/messages",
            json={"content": content, "question": question},
            headers=self.as_user(user),
        )

    def check(self, question: str, answer: str, user: str = "alex"):
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/check",
            json={"question": question, "answer": answer},
            headers=self.as_user(user),
        )

    def detail(self) -> dict:
        path = f"/api/chat/conversations/{self.chat_id}"
        return self.client.get(path, headers=self.as_user("alex")).json()

    def progress(self) -> dict:
        return {p["number"]: p for p in self.detail()["progress"]}


@pytest.fixture
def h() -> LessonPageHarness:
    return LessonPageHarness()


def test_students_see_the_worksheet_but_never_its_answers(h):
    lesson = h.detail()["lesson"]
    assert lesson["support"] == "step_by_step"
    assert lesson["worked_examples"] == [
        {"title": "Elimination", "text": "Subtract to remove $y$."}
    ]
    assert lesson["questions"][0] == {"number": "A1.1", "text": QUESTIONS[0]["text"]}
    assert KEY not in json.dumps(h.detail())


def test_a_question_and_its_answer_join_only_that_turn(h):
    h.ask("I'm stuck", question="A1.1")
    tagged_call = h.model.calls[-1]
    assert QUESTIONS[0]["text"] in tagged_call[-2].content
    assert KEY in tagged_call[-2].content and "Never reveal it" in tagged_call[-2].content
    assert KEY not in tagged_call[0].content

    h.ask("And now?")
    assert all(KEY not in m.content for m in h.model.calls[-1])
    stored = h.store.get_conversation("alex", h.chat_id).messages
    assert [m.question for m in stored if m.role == "user"] == ["A1.1", None]
    assert all(KEY not in m.content for m in stored)


def test_an_unknown_question_is_ignored(h):
    h.ask("help", question="Z9")
    assert h.store.get_conversation("alex", h.chat_id).messages[0].question is None


def test_an_exact_answer_is_correct_without_a_model_call(h):
    response = h.check("A1.1", " x = 7,  y = 4 ")
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert h.model.calls == []
    assert {p["number"]: p["status"] for p in body["progress"]}["A1.1"] == "correct"
    *_, mine, reply = h.store.get_conversation("alex", h.chat_id).messages
    assert (mine.question, mine.checks_answer, reply.question) == ("A1.1", True, "A1.1")


def test_other_answers_are_checked_by_the_model_and_charged_to_the_student(h):
    h.model.reply = [json.dumps({"correct": False, "feedback": "Check the signs in step 2."})]
    body = h.check("A1.1", "x = 6, y = 5").json()
    assert body == {
        "correct": False,
        "feedback": "Check the signs in step 2.",
        "progress": body["progress"],
    }
    assert h.model.output_caps == [CHECK_OUTPUT_TOKENS]
    assert "<student_answer>\nx = 6, y = 5\n</student_answer>" in h.model.calls[0][-1].content
    assert h.store.cost_used("alex", FIXED_NOW.date()) == LUNA.cost_micro_usd(h.model.usage)
    [attempt] = h.store.get_conversation("alex", h.chat_id).attempts
    assert (attempt.question, attempt.correct) == ("A1.1", False)


def test_feedback_that_gives_the_answer_away_is_replaced(h):
    h.model.reply = [json.dumps({"correct": False, "feedback": "Close! It's $x=7$, $y=4$."})]
    assert h.check("A1.1", "x = 7, y = 5").json()["feedback"] == NOT_YET


def test_a_question_without_an_answer_key_cannot_be_checked(h):
    response = h.check("A2.5", "17 and 9")
    assert response.status_code == 409 and response.json()["detail"] == NO_KEY
    assert h.store.get_conversation("alex", h.chat_id).attempts == []


def test_bad_checks_are_refused(h):
    assert h.check("Z9", "1").status_code == 404
    assert h.check("A1.1", "   ").status_code == 400
    h.model.reply = ["I think it's fine?"]
    assert h.check("A1.1", "x = 1").status_code == 502
    assert h.store.get_conversation("alex", h.chat_id).attempts == []


def test_only_the_student_can_check_answers_in_their_chat(h):
    assert h.check("A1.1", "x = 7, y = 4", user="sam").status_code == 404
    assert h.check("A1.1", "x = 7, y = 4", user="bea").status_code == 404
    path = f"/api/chat/conversations/{h.chat_id}/check"
    assert h.client.post(path, json={"question": "A1.1", "answer": "1"}).status_code == 401


def test_the_kill_switch_stops_model_checks_but_not_exact_matches():
    h = LessonPageHarness(limits=ChatLimits(enabled=False))
    assert h.check("A1.1", "x=7, y=4").json()["correct"] is True
    assert h.check("A1.2", "x = 1").status_code == 503


def test_progress_counts_help_and_attempts_per_question(h):
    h.ask("What is this asking?", question="A1.2")
    h.ask("Give me a hint", question="A1.2")
    h.check("A1.1", "x=7,y=4")
    progress = h.progress()
    assert progress["A1.1"] == {
        "number": "A1.1",
        "status": "correct",
        "attempts": 1,
        "help_messages": 0,
    }
    assert progress["A1.2"] == {
        "number": "A1.2",
        "status": "working",
        "attempts": 0,
        "help_messages": 2,
    }
    assert progress["A2.5"]["status"] == "not_started"
    tutor_view = h.client.get(f"/api/students/alex/chats/{h.chat_id}", headers=h.as_user("sam"))
    assert tutor_view.json()["progress"] == h.detail()["progress"]


@pytest.mark.parametrize(
    ("answer", "key", "expected"),
    [
        ("x = 7, y = 4", "$x=7$, $y=4$", True),
        ("X=7,Y=4.", "$x = 7$, $y = 4$", True),
        ("10 km", "10 km", True),
        ("x = 4, y = 7", "$x=7$, $y=4$", False),
        ("", "4", False),
    ],
)
def test_exact_matching_ignores_only_formatting(answer, key, expected):
    assert matches_key(answer, key) is expected


def test_the_leak_guard_matches_whole_answers_only():
    assert leaks_key("The answer is $030°$ here", "$030°$")
    assert leaks_key("so it's 10 km", "10 km")
    assert not leaks_key("Look at step 4 again.", "40")
    assert not leaks_key("Check question 14.", "4")
