import json

import pytest

from prof_ai.chat.checking import CHECK_OUTPUT_TOKENS
from prof_ai.chat.service import ChatLimits
from prof_ai.lessons.first_steps import FIRST_STEPS_OUTPUT_TOKENS
from tests.lessons.conftest import RATIOS, LessonHarness

FIRST_STEP = "$x^2 + 9x + 14 = (x + \\square)(x + \\square)$"
QUESTIONS = [
    {
        "number": "1",
        "text": "Solve $x^2 + 9x + 14 = 0$.",
        "answer": "$x = -2$ or $x = -7$",
        "first_step": FIRST_STEP,
    },
    {"number": "2", "text": "Solve $x^2 - 9 = 0$.", "answer": "$x = 3$ or $x = -3$"},
]
LESSON = {**RATIOS, "material": "", "support": "step_by_step", "questions": QUESTIONS}
WORKING = ["$(x+7)(x+2)=0$"]


class WorkspaceHarness(LessonHarness):
    def __init__(self, lesson: dict | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.chat_id = self.create("sam", "alex", lesson or LESSON).json()["id"]

    def detail(self, user: str = "alex") -> dict:
        path = (
            f"/api/chat/conversations/{self.chat_id}"
            if user == "alex"
            else f"/api/students/alex/chats/{self.chat_id}"
        )
        return self.client.get(path, headers=self.as_user(user)).json()

    def set_support(self, support: str) -> None:
        response = self.client.patch(
            f"/api/students/alex/chats/{self.chat_id}",
            json={"support": support},
            headers=self.as_user("sam"),
        )
        assert response.status_code == 200

    def submit(self, working=None, answer="$x=-2$ or $x=-7$", verdict="correct"):
        self.model.reply = [json.dumps({"verdict": verdict, "feedback": ""})]
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/check",
            json={
                "question": "1",
                "working": WORKING if working is None else working,
                "answer": answer,
            },
            headers=self.as_user("alex"),
        )

    def check_working(self):
        self.model.reply = [json.dumps({"feedback": "Good start."})]
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/working",
            json={"question": "1", "working": WORKING},
            headers=self.as_user("alex"),
        )

    def draft(self, user: str, questions: list[dict]):
        return self.client.post(
            "/api/lessons/first-steps", json={"questions": questions}, headers=self.as_user(user)
        )


@pytest.fixture
def h() -> WorkspaceHarness:
    return WorkspaceHarness()


def test_students_get_first_steps_only_at_step_by_step(h):
    assert h.detail()["lesson"]["first_steps"] == {"1": FIRST_STEP}
    h.set_support("balanced")
    assert "first_steps" not in h.detail()["lesson"]
    assert "$x = -2$" not in json.dumps(h.detail())


def test_a_drafted_first_step_must_be_confirmed_before_saving(h):
    drafted = [{**QUESTIONS[0], "first_step_needs_review": True}]
    response = h.create("sam", "alex", {**LESSON, "questions": drafted})
    assert response.status_code == 400
    assert "Check the first steps Prof AI drafted before saving: 1." in response.json()["detail"]


def test_only_tutors_can_draft_first_steps(h):
    assert h.draft("alex", QUESTIONS).status_code == 403


def test_drafts_that_give_the_answer_away_are_dropped(h):
    h.model.reply = [
        json.dumps(
            {
                "first_steps": [
                    {"number": "2", "first_step": "$x^2 = 9$, so $x = 3$ or $x = -3$"},
                    {"number": "1", "first_step": FIRST_STEP},
                    {"number": "99", "first_step": "not asked for"},
                ]
            }
        )
    ]
    response = h.draft("sam", QUESTIONS)
    assert response.status_code == 200
    assert response.json() == {
        "first_steps": [
            {"number": "1", "first_step": FIRST_STEP},
            {"number": "2", "first_step": None},
        ]
    }
    assert h.model.output_caps[-1] == FIRST_STEPS_OUTPUT_TOKENS
    sent = h.model.calls[-1][1].content
    assert "Solve $x^2 + 9x + 14 = 0$." in sent and "Answer: $x = -2$ or $x = -7$" in sent


def test_drafts_too_long_for_one_line_are_dropped(h):
    h.model.reply = [json.dumps({"first_steps": [{"number": "1", "first_step": "x" * 301}]})]
    assert h.draft("sam", QUESTIONS[:1]).json()["first_steps"] == [
        {"number": "1", "first_step": None}
    ]


def test_drafting_respects_the_kill_switch():
    h = WorkspaceHarness(limits=ChatLimits(enabled=False))
    assert h.draft("sam", QUESTIONS).status_code == 503


def test_marking_and_hints_know_which_line_was_given(h):
    assert h.submit().status_code == 200
    assert f"<given_first_step>\n{FIRST_STEP}\n</given_first_step>" in h.model.calls[-1][1].content
    assert h.check_working().status_code == 200
    assert "<given_first_step>" in h.model.calls[-1][1].content
    h.set_support("stretch")
    h.submit()
    assert "<given_first_step>" not in h.model.calls[-1][1].content


def test_a_chat_turn_about_the_question_mentions_the_given_line(h):
    h.client.post(
        f"/api/chat/conversations/{h.chat_id}/messages",
        json={"content": "I'm stuck", "question": "1"},
        headers=h.as_user("alex"),
    )
    sent = "\n".join(m.content for m in h.model.calls[-1])
    assert f"which they were given:\n{FIRST_STEP}" in sent


def test_the_given_line_never_counts_as_the_students_working(h):
    calls = len(h.model.calls)
    response = h.submit(working=[])
    assert response.status_code == 400
    assert "Show your working first" in response.json()["detail"]
    assert len(h.model.calls) == calls


def test_the_student_and_their_tutor_see_each_attempt(h):
    assert "attempts" not in h.detail()
    h.submit(answer="$x=2$ or $x=7$", verdict="slip")
    for user in ("alex", "sam"):
        [attempt] = h.detail(user)["attempts"]
        assert attempt["question"] == "1"
        assert attempt["working"] == WORKING
        assert attempt["answer"] == "$x=2$ or $x=7$"
        assert (attempt["verdict"], attempt["correct"], attempt["verified"]) == (
            "slip",
            False,
            True,
        )
    other_tutor = h.client.get(f"/api/students/alex/chats/{h.chat_id}", headers=h.as_user("punji"))
    assert other_tutor.status_code == 404


def test_marking_and_hints_leave_room_to_reason_before_replying(h):
    # A reasoning model spends part of the output cap thinking; at 300 tokens a reply about
    # an impossible second root was cut off mid-JSON and the student saw an error.
    assert h.submit().status_code == 200
    assert h.check_working().status_code == 200
    assert h.model.output_caps[-2:] == [CHECK_OUTPUT_TOKENS, CHECK_OUTPUT_TOKENS]
    assert CHECK_OUTPUT_TOKENS >= 1_000
