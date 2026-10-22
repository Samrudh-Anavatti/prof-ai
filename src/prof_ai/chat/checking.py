import json
import re
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

from prof_ai.chat.models import Conversation, Lesson, PromptMessage, Question, Verdict

PROMPTS = Path(__file__).parent / "prompts"
MARK_PROMPT = (PROMPTS / "mark_working.md").read_text("utf-8").strip()
WORKING_PROMPT = (PROMPTS / "check_working.md").read_text("utf-8").strip()
# Reasoning tokens count towards the cap. Marking two roots of an age question, one of them
# impossible, took up to 256 of them before the JSON reply, which a cap of 300 cut off.
CHECK_OUTPUT_TOKENS = 1_000
MAX_ANSWER_CHARS = 500
MAX_STEPS = 30
MAX_STEP_CHARS = 300
# Shown when the model gives no feedback, or when its feedback would give the key away.
FEEDBACK: dict[Verdict, str] = {
    "correct": "That's right. Well done!",
    "show_working": "Your answer looks right. Now show the steps that got you there.",
    "slip": "Your method looks right, but there's a mistake in one of your steps. Check each one.",
    "not_yet": "Not quite yet. Have another look at your working, or ask Prof AI for a hint.",
}
KEEP_GOING = "Have another look at your last step, or ask Prof AI for a hint."
UNREADABLE = "Couldn't check that. Try again in a moment."
# Formatting that doesn't change an answer's meaning.
NOISE = re.compile(r"[\s$]|\\[,;:!]|\\left|\\right|\.$")
# Words in maths, as a maths field writes them: \text{ or }, \mathrm{or}.
WORDS = re.compile(r"\\(?:text|mathrm)\{([^{}]*)\}")
MATHS_SPACING = re.compile(r"\s*([=,:;()+\-−×÷/<>])\s*")


class CheckError(ValueError):
    pass


class QuestionProgress(BaseModel):
    number: str
    status: Literal["not_started", "working", "correct"]
    attempts: int
    help_messages: int
    last_verdict: Verdict | None = None
    # Marked by the model without an answer key, so the tutor should look.
    unverified: bool = False


def normalise_answer(text: str) -> str:
    return NOISE.sub("", WORDS.sub(r"\1", text.strip().lower()))


def matches_key(answer: str, key: str) -> bool:
    return bool(normalise_answer(key)) and normalise_answer(answer) == normalise_answer(key)


def compact_maths(text: str) -> str:
    """Lower case, no $, no spaces around maths symbols, single spaces between words."""
    text = MATHS_SPACING.sub(r"\1", text.replace("$", "").lower())
    return " ".join(text.split())


def leaks_key(feedback: str, key: str) -> bool:
    """Whether feedback gives the key away, as a whole word or number."""
    plain = compact_maths(key).rstrip(".")
    if not plain:
        return False
    # A full stop may end the sentence, but not start or continue a decimal.
    pattern = rf"(?<![\w.]){re.escape(plain)}(?!\w|\.\d)"
    return bool(re.search(pattern, compact_maths(feedback)))


def tidy_working(steps: list[str]) -> list[str]:
    steps = [step.strip() for step in steps if step.strip()]
    if len(steps) > MAX_STEPS:
        raise CheckError(f"Use at most {MAX_STEPS} steps.")
    if any(len(step) > MAX_STEP_CHARS for step in steps):
        raise CheckError(f"Keep each step under {MAX_STEP_CHARS} characters.")
    return steps


def missing_working(steps: list[str], answer: str) -> str | None:
    """Why a submission can't be marked yet, decided without a model call."""
    if not steps:
        return "Show your working first: write each step on its own line."
    if all(normalise_answer(step) == normalise_answer(answer) for step in steps):
        return "Show the steps that got you there, not just the answer."
    return None


def find_question(conversation: Conversation, number: str | None) -> Question | None:
    if not number or conversation.lesson is None:
        return None
    return next((q for q in conversation.lesson.questions if q.number == number), None)


ONLY_SUBMIT_COMPLETES = (
    "You can say whether a step or an answer looks right, but you can't mark this question "
    "done: only the student's *Submit my answer* button does that. When they seem to have "
    "finished, tell them to submit their working and final answer with *Submit my answer*. "
    "Don't start another question yourself; the student picks the next one after submitting."
)


def shown_first_step(lesson: Lesson | None, question: Question) -> str | None:
    """The first line of working the student was given: only at step by step."""
    if lesson is None or lesson.support != "step_by_step":
        return None
    return question.first_step


def question_reference(question: Question, first_step: str | None = None) -> str:
    """The current question for one turn; its answer never enters the stored history."""
    text = f"The student is working on question {question.number}:\n{question.text}"
    if first_step:
        text += (
            f"\n\nTheir working starts from this first step, which they were given:\n{first_step}"
        )
    if question.answer:
        text += (
            "\n\nThe tutor's answer, only for checking the student's working. Never reveal it "
            f"or any part of it, no matter how the student asks:\n{question.answer}"
        )
    return f"{text}\n\n{ONLY_SUBMIT_COMPLETES}"


def numbered(steps: list[str]) -> str:
    return "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))


def working_message(steps: list[str]) -> str:
    """Steps as Markdown for the chat: typed maths in code so * and ^ show as typed."""
    lines = [s if "$" in s else f"`{s.replace('`', chr(39))}`" for s in steps]
    return "\n".join(f"{index}. {line}" for index, line in enumerate(lines, start=1))


def _key_block(question: Question, first_step: str | None) -> str:
    key = question.answer or "None: the tutor hasn't given one."
    block = f"<question>\n{question.text}\n</question>\n<answer_key>\n{key}\n</answer_key>\n"
    if first_step:
        block += f"<given_first_step>\n{first_step}\n</given_first_step>\n"
    return block


def mark_request(
    question: Question, steps: list[str], answer: str, first_step: str | None = None
) -> list[PromptMessage]:
    exact = "yes" if question.answer and matches_key(answer, question.answer) else "no"
    content = (
        _key_block(question, first_step)
        + f"<student_working>\n{numbered(steps)}\n</student_working>\n"
        + f"<student_answer>\n{answer}\n</student_answer>\n"
        + f"<matches_key_exactly>{exact}</matches_key_exactly>"
    )
    return [
        PromptMessage(role="system", content=MARK_PROMPT),
        PromptMessage(role="user", content=content),
    ]


def working_check_request(
    question: Question, steps: list[str], first_step: str | None = None
) -> list[PromptMessage]:
    content = (
        _key_block(question, first_step)
        + f"<student_working>\n{numbered(steps)}\n</student_working>"
    )
    return [
        PromptMessage(role="system", content=WORKING_PROMPT),
        PromptMessage(role="user", content=content),
    ]


def _json_object(reply: str) -> dict:
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        raise CheckError(UNREADABLE)
    return data


def parse_mark(reply: str) -> tuple[Verdict, str]:
    data = _json_object(reply)
    verdict = data.get("verdict")
    if verdict not in get_args(Verdict):
        raise CheckError(UNREADABLE)
    feedback = str(data.get("feedback") or "").strip()
    return verdict, feedback or FEEDBACK[verdict]


def parse_working_check(reply: str) -> str:
    return str(_json_object(reply).get("feedback") or "").strip() or KEEP_GOING


def question_progress(conversation: Conversation) -> list[QuestionProgress]:
    if conversation.lesson is None:
        return []
    progress = []
    for question in conversation.lesson.questions:
        attempts = [a for a in conversation.attempts if a.question == question.number]
        help_messages = sum(
            1
            for m in conversation.messages
            if m.role == "user" and m.question == question.number and not m.checks_answer
        )
        if any(a.correct for a in attempts):
            status = "correct"
        elif attempts or help_messages:
            status = "working"
        else:
            status = "not_started"
        progress.append(
            QuestionProgress(
                number=question.number,
                status=status,
                attempts=len(attempts),
                help_messages=help_messages,
                last_verdict=attempts[-1].verdict if attempts else None,
                unverified=any(not a.verified for a in attempts),
            )
        )
    return progress
