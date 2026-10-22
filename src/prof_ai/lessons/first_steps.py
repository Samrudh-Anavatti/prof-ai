import json
from pathlib import Path

from pydantic import BaseModel, Field

from prof_ai.chat.checking import MAX_STEP_CHARS, leaks_key
from prof_ai.chat.context import estimate_tokens
from prof_ai.chat.models import PromptMessage
from prof_ai.lessons.worksheet import MAX_WORKSHEET_TOKENS

FIRST_STEPS_PROMPT = (
    (Path(__file__).parent / "prompts" / "first_steps.md").read_text(encoding="utf-8").strip()
)
# One short line for each of up to 60 questions.
FIRST_STEPS_OUTPUT_TOKENS = 4_000
UNREADABLE = "Couldn't draft the first steps. Try again, or write them by hand."


class FirstStepsError(ValueError):
    pass


class QuestionToStart(BaseModel):
    number: str = Field(max_length=20)
    text: str = Field(max_length=4_000)
    # The tutor's answer, so the step heads the right way and can be checked for leaks.
    answer: str | None = Field(default=None, max_length=1_000)


class FirstStep(BaseModel):
    number: str
    first_step: str | None


def _question_block(question: QuestionToStart) -> str:
    block = f"{question.number}. {question.text.strip()}"
    if (question.answer or "").strip():
        block += f"\nAnswer: {question.answer.strip()}"
    return block


def first_steps_request(questions: list[QuestionToStart]) -> list[PromptMessage]:
    questions = [q for q in questions if q.text.strip()]
    if not questions:
        raise FirstStepsError("Add some questions first.")
    text = "\n\n".join(_question_block(q) for q in questions)
    if estimate_tokens(text) > MAX_WORKSHEET_TOKENS:
        raise FirstStepsError("Those questions are too long to do at once. Do fewer at a time.")
    return [
        PromptMessage(role="system", content=FIRST_STEPS_PROMPT),
        PromptMessage(role="user", content=f"<questions>\n{text}\n</questions>"),
    ]


def parse_first_steps(reply: str, questions: list[QuestionToStart]) -> list[FirstStep]:
    """One step per asked-for question, in order. A step that gives the answer away is dropped,
    and so is one too long to be a single line of working."""
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        data = None
    entries = data.get("first_steps") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise FirstStepsError(UNREADABLE)
    asked = {q.number: q for q in questions if q.text.strip()}
    found: dict[str, str | None] = {}
    for entry in entries:
        if not isinstance(entry, dict) or str(entry.get("number")) not in asked:
            continue
        number = str(entry["number"])
        step = entry.get("first_step")
        text = step.strip() if isinstance(step, str) else ""
        key = asked[number].answer
        if len(text) > MAX_STEP_CHARS or (key and leaks_key(text, key)):
            text = ""
        found[number] = text or None
    return [FirstStep(number=number, first_step=found.get(number)) for number in asked]
