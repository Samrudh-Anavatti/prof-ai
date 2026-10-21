import json

import pytest

from prof_ai.chat.checking import CHECK_OUTPUT_TOKENS, FEEDBACK, KEEP_GOING, MAX_STEPS
from prof_ai.chat.model_profiles import GLM_FLASH, LUNA
from prof_ai.chat.service import ChatLimits
from prof_ai.lessons.answers import SOLVE_OUTPUT_TOKENS
from tests.lessons.conftest import RATIOS
from tests.model_providers.test_model_providers import ProvidersHarness
from tests.student_lesson_page.test_student_lesson_page import QUESTIONS, LessonPageHarness
from tests.tutor_chat.conftest import FIXED_NOW

WORKING = ["x + y = 11", "x - y = 3", "add them: 2x = 14", "x = 7, y = 4"]


class WorkingHarness(LessonPageHarness):
    def submit(self, question="A1.1", working=None, answer="x = 7, y = 4", user="alex"):
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/check",
            json={
                "question": question,
                "working": WORKING if working is None else working,
                "answer": answer,
            },
            headers=self.as_user(user),
        )

    def check_working(self, question="A1.1", working=None, user="alex"):
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/working",
            json={"question": question, "working": WORKING[:2] if working is None else working},
            headers=self.as_user(user),
        )

    def marks(self, verdict: str, feedback: str = "") -> None:
        self.model.reply = [json.dumps({"verdict": verdict, "feedback": feedback})]

    def stored(self):
        return self.store.get_conversation("alex", self.chat_id)


@pytest.fixture
def h() -> WorkingHarness:
    return WorkingHarness()


@pytest.mark.parametrize(
    ("working", "answer", "message"),
    [
        ([], "x = 7, y = 4", "Show your working first"),
        (["  ", ""], "x = 7, y = 4", "Show your working first"),
        (["x=7,y=4"], "x = 7, y = 4", "not just the answer"),
        (["x + y = 11"], "  ", "final answer first"),
        (["1"] * (MAX_STEPS + 1), "1", f"at most {MAX_STEPS} steps"),
        (["x" * 301], "1", "under 300 characters"),
    ],
)
def test_missing_working_is_refused_without_a_model_call(h, working, answer, message):
    response = h.submit(working=working, answer=answer)
    assert response.status_code == 400 and message in response.json()["detail"]
    assert h.model.calls == [] and h.stored().attempts == []


@pytest.mark.parametrize("verdict", ["correct", "show_working", "slip", "not_yet"])
def test_each_verdict_is_returned_and_recorded_with_the_working(h, verdict):
    h.marks(verdict, "Look again at step 3.")
    body = h.submit(answer="x = 6, y = 5").json()
    assert (body["verdict"], body["correct"]) == (verdict, verdict == "correct")
    assert body["feedback"] == "Look again at step 3."
    [attempt] = h.stored().attempts
    assert attempt.working == WORKING and attempt.answer == "x = 6, y = 5"
    assert (attempt.verdict, attempt.correct, attempt.verified) == (
        verdict,
        verdict == "correct",
        True,
    )
    *_, mine, reply = h.stored().messages
    assert mine.checks_answer and mine.question == "A1.1" and "1. `x + y = 11`" in mine.content
    assert reply.content == "Look again at step 3."
    progress = {p["number"]: p for p in body["progress"]}["A1.1"]
    assert progress["last_verdict"] == verdict


def test_the_model_marks_the_numbered_working_against_the_key_and_the_student_pays(h):
    h.marks("correct")
    h.submit()
    prompt = h.model.calls[0][-1].content
    assert "<answer_key>\n$x=7$, $y=4$\n</answer_key>" in prompt
    assert "1. x + y = 11\n2. x - y = 3" in prompt
    assert "<matches_key_exactly>yes</matches_key_exactly>" in prompt
    assert h.model.output_caps == [CHECK_OUTPUT_TOKENS]
    assert h.store.cost_used("alex", FIXED_NOW.date()) == LUNA.cost_micro_usd(h.model.usage)


@pytest.mark.parametrize("verdict", ["slip", "not_yet"])
def test_a_right_answer_is_never_marked_wrong_only_missing_working(h, verdict):
    h.marks(verdict, "Check step 2.")
    body = h.submit(answer="$x = 7$, $y = 4$").json()
    assert body["verdict"] == "show_working"
    assert body["feedback"] == FEEDBACK["show_working"]


@pytest.mark.parametrize("verdict", ["show_working", "slip", "not_yet"])
def test_feedback_that_gives_the_answer_away_is_replaced(h, verdict):
    h.marks(verdict, "Nearly! It should be $x=7$, $y=4$.")
    assert h.submit(answer="x = 7, y = 5").json()["feedback"] == FEEDBACK[verdict]


def test_a_question_without_a_key_is_marked_but_unverified(h):
    h.marks("correct", "Well reasoned.")
    body = h.submit(
        question="A2.5", working=["a + b = 26", "a - b = 8", "a = 17"], answer="17, 9"
    ).json()
    assert body["verdict"] == "correct"
    assert "None: the tutor hasn't given one." in h.model.calls[0][-1].content
    assert h.stored().attempts[0].verified is False
    assert {p["number"]: p for p in body["progress"]}["A2.5"]["unverified"] is True


def test_checking_working_so_far_is_help_not_an_attempt(h):
    h.model.reply = [json.dumps({"feedback": "Good so far. What happens if you add them?"})]
    response = h.check_working()
    assert response.status_code == 200
    assert response.json()["feedback"] == "Good so far. What happens if you add them?"
    assert "1. x + y = 11\n2. x - y = 3" in h.model.calls[0][-1].content
    assert h.stored().attempts == []
    progress = {p["number"]: p for p in response.json()["progress"]}["A1.1"]
    assert (progress["status"], progress["attempts"], progress["help_messages"]) == (
        "working",
        0,
        1,
    )


def test_working_check_feedback_never_gives_the_answer_away(h):
    h.model.reply = [json.dumps({"feedback": "You'll end with $x = 7$, $y = 4$."})]
    assert h.check_working().json()["feedback"] == KEEP_GOING
    assert h.check_working(working=[" "]).status_code == 400


def test_unreadable_marks_are_an_error_and_nothing_is_recorded(h):
    h.model.reply = ["Looks fine to me!"]
    assert h.submit().status_code == 502
    h.model.reply = [json.dumps({"verdict": "brilliant", "feedback": "x"})]
    assert h.submit().status_code == 502
    assert h.stored().attempts == [] and h.stored().messages == []


def test_the_kill_switch_stops_every_check():
    h = WorkingHarness(limits=ChatLimits(enabled=False))
    assert h.submit().status_code == 503
    assert h.check_working().status_code == 503
    assert h.model.calls == []


def test_only_the_student_can_submit_or_check_in_their_chat(h):
    for user in ("sam", "bea"):
        assert h.submit(user=user).status_code == 404
        assert h.check_working(user=user).status_code == 404
    assert h.submit(question="Z9").status_code == 404
    path = f"/api/chat/conversations/{h.chat_id}/working"
    assert h.client.post(path, json={"question": "A1.1", "working": ["1"]}).status_code == 401


def solve(h, questions, actor="sam"):
    return h.client.post(
        "/api/lessons/answers", json={"questions": questions}, headers=h.as_user(actor)
    )


def test_a_tutor_gets_missing_answers_worked_out_and_pays_for_it():
    h = WorkingHarness()
    h.model.reply = [
        json.dumps(
            {
                "answers": [
                    {"number": "A2.6", "answer": None},
                    {"number": "A2.5", "answer": "$17$ and $9$"},
                    {"number": "Z1", "answer": "invented"},
                ]
            }
        )
    ]
    questions = [{"number": "A2.5", "text": QUESTIONS[2]["text"]}, {"number": "A2.6", "text": "?"}]
    response = solve(h, questions)
    assert response.status_code == 200
    assert response.json() == {
        "answers": [
            {"number": "A2.5", "answer": "$17$ and $9$"},
            {"number": "A2.6", "answer": None},
        ]
    }
    assert "A2.5. Two numbers sum to 26" in h.model.calls[-1][-1].content
    assert h.model.output_caps[-1] == SOLVE_OUTPUT_TOKENS
    assert h.store.cost_used("sam", FIXED_NOW.date()) > 0


def test_solving_is_for_tutors_and_may_use_their_preferred_model():
    h = ProvidersHarness()
    h.glm.reply = [json.dumps({"answers": [{"number": "1", "answer": "$4$"}]})]
    h.prefer(GLM_FLASH.deployment)
    assert solve(h, [{"number": "1", "text": "2 + 2"}]).json()["answers"][0]["answer"] == "$4$"
    assert len(h.glm.calls) == 1
    assert solve(h, [{"number": "1", "text": "2 + 2"}], actor="alex").status_code == 403
    assert h.client.post("/api/lessons/answers", json={"questions": []}).status_code == 401
    assert solve(h, []).status_code == 400


def test_a_lesson_cant_be_saved_until_worked_out_answers_are_checked(h):
    unchecked = {**QUESTIONS[2], "answer": "$17$ and $9$", "answer_needs_review": True}
    lesson = {**RATIOS, "questions": [unchecked]}
    response = h.create("sam", "alex", lesson, licence=True)
    assert response.status_code == 400 and "A2.5" in response.json()["detail"]
    checked = {**unchecked, "answer_needs_review": False}
    assert h.create("sam", "alex", {**RATIOS, "questions": [checked]}).status_code == 201
