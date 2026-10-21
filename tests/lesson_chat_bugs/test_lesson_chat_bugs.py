import pytest

from prof_ai.chat.checking import question_reference
from prof_ai.chat.model_profiles import LUNA
from prof_ai.chat.models import Question
from prof_ai.chat.prompts import BASE_PROMPT
from prof_ai.evals.dilution import DilutionEval, load_scenarios
from tests.lessons.conftest import RATIOS, LessonHarness

WORKSHEET = {
    **RATIOS,
    "material": "",
    "questions": [
        {"number": "1", "text": "Share 35 sweets in the ratio 2:5.", "answer": "10 and 25"},
        {"number": "2", "text": "Simplify 18:24.", "answer": "3:4"},
    ],
}


class BugsHarness(LessonHarness):
    def lesson_chat(self, actor: str, owner: str) -> str:
        return self.create(actor, owner, WORKSHEET).json()["id"]

    def say(self, user: str, chat_id: str, content: str, question: str | None = None):
        return self.client.post(
            f"/api/chat/conversations/{chat_id}/messages",
            json={"content": content, "question": question},
            headers=self.as_user(user),
        )

    def messages(self, user: str, chat_id: str) -> list[dict]:
        path = f"/api/chat/conversations/{chat_id}"
        return self.client.get(path, headers=self.as_user(user)).json()["messages"]


@pytest.fixture
def h() -> BugsHarness:
    return BugsHarness()


def test_only_submitting_completes_a_question_in_the_turn_and_the_base_prompt():
    reference = question_reference(Question(number="1", text="Share 35 sweets.", answer="10"))
    assert "*Submit my answer*" in reference
    assert "Don't start another question" in reference
    assert "only the student's *Submit my answer* button marks a question done" in BASE_PROMPT


def test_a_reply_is_saved_with_the_question_it_answers(h):
    chat_id = h.lesson_chat("sam", "alex")
    h.model.reply = ["Nearly there."]
    h.say("alex", chat_id, "Is it 10 and 25?", question="2")
    messages = h.messages("alex", chat_id)
    assert [(m["author"], m["question"]) for m in messages] == [("student", "2"), ("ai", "2")]


def test_a_tutor_trying_a_lesson_on_themselves_gets_prof_ai_without_at_ai(h):
    chat_id = h.lesson_chat("sam", "sam")
    h.model.reply = ["Let's start with the parts."]
    h.say("sam", chat_id, "How do I start?", question="1")
    assert [m["author"] for m in h.messages("sam", chat_id)] == ["tutor", "ai"]
    assert len(h.model.calls) == 1


def test_a_tutor_in_their_students_chat_still_needs_at_ai(h):
    chat_id = h.lesson_chat("sam", "alex")
    path = f"/api/students/alex/chats/{chat_id}/messages"
    h.client.post(path, json={"content": "Try Q2 next"}, headers=h.as_user("sam"))
    assert h.model.calls == []


def test_the_premature_done_case_sends_its_question_with_the_turn():
    case = next(s for s in load_scenarios() if s.id == "premature-done")
    assert case.question is not None and case.must_contain_any

    class Recorder:
        def __init__(self) -> None:
            self.calls: list = []

        def stream(self, messages, max_output_tokens):
            self.calls.append(messages)
            raise RuntimeError("stop after recording")

    recorder = Recorder()
    DilutionEval(recorder, LUNA, max_usd=1).run_case(case, "Lesson text.", 2_000, 0)
    sent = "\n".join(m.content for m in recorder.calls[0])
    assert case.question.text in sent and "*Submit my answer*" in sent
