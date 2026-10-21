import json
from pathlib import Path

from pydantic import BaseModel, Field

from prof_ai.chat.context import estimate_tokens
from prof_ai.chat.models import PromptMessage
from prof_ai.lessons.worksheet import MAX_WORKSHEET_TOKENS

SOLVE_PROMPT = (
    (Path(__file__).parent / "prompts" / "solve_questions.md").read_text(encoding="utf-8").strip()
)
# Final answers only, for up to 60 questions.
SOLVE_OUTPUT_TOKENS = 3_000
MAX_ANSWER_CHARS = 1_000
UNREADABLE = "Couldn't work out the answers. Try again, or add them by hand."


class AnswersError(ValueError):
    pass


class QuestionToSolve(BaseModel):
    number: str = Field(max_length=20)
    text: str = Field(max_length=4_000)


class SolvedAnswer(BaseModel):
    number: str
    answer: str | None


def solve_request(questions: list[QuestionToSolve]) -> list[PromptMessage]:
    questions = [q for q in questions if q.text.strip()]
    if not questions:
        raise AnswersError("Every question already has an answer.")
    text = "\n\n".join(f"{q.number}. {q.text.strip()}" for q in questions)
    if estimate_tokens(text) > MAX_WORKSHEET_TOKENS:
        raise AnswersError("Those questions are too long to solve at once. Do fewer at a time.")
    return [
        PromptMessage(role="system", content=SOLVE_PROMPT),
        PromptMessage(role="user", content=f"<questions>\n{text}\n</questions>"),
    ]


def parse_answers(reply: str, numbers: list[str]) -> list[SolvedAnswer]:
    """One answer per asked-for number, in the order asked; anything else is dropped."""
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        data = None
    entries = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise AnswersError(UNREADABLE)
    found: dict[str, str | None] = {}
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("number")) in numbers:
            answer = entry.get("answer")
            text = answer.strip()[:MAX_ANSWER_CHARS] if isinstance(answer, str) else ""
            found[str(entry["number"])] = text or None
    return [SolvedAnswer(number=n, answer=found.get(n)) for n in numbers]
