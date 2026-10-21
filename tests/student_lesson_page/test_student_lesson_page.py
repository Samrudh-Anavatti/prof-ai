import json

import pytest

from prof_ai.chat.checking import leaks_key, matches_key
from tests.lessons.conftest import RATIOS, LessonHarness

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

    def check(
        self,
        question: str,
        answer: str,
        working: list[str] | None = None,
        user: str = "alex",
        verdict: str = "correct",
    ):
        self.model.reply = [json.dumps({"verdict": verdict, "feedback": ""})]
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/check",
            json={"question": question, "working": working or ["x + y = 11"], "answer": answer},
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
        "last_verdict": "correct",
        "unverified": False,
    }
    assert progress["A1.2"] == {
        "number": "A1.2",
        "status": "working",
        "attempts": 0,
        "help_messages": 2,
        "last_verdict": None,
        "unverified": False,
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
