import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from prof_ai.chat.context import LAYER_CAPS, Layer, estimate_tokens
from prof_ai.chat.models import PromptMessage, Question, WorkedExample

EXTRACT_PROMPT = (
    (Path(__file__).parent / "prompts" / "extract_worksheet.md").read_text(encoding="utf-8").strip()
)
# Worksheet text is lesson material, so it gets the lesson layer's allowance.
MAX_WORKSHEET_TOKENS = LAYER_CAPS[Layer.LESSON]
# Room for every question, answer and worked step of a long worksheet, inside ADR 0005's
# 8k output reserve.
EXTRACT_OUTPUT_TOKENS = 6_000


class WorksheetError(ValueError):
    pass


class Worksheet(BaseModel):
    title: str = Field(default="", max_length=120)
    topics: list[str] = Field(default=[], max_length=20)
    worked_examples: list[WorkedExample] = Field(default=[], max_length=10)
    questions: list[Question] = Field(default=[], max_length=60)


def extraction_request(text: str) -> list[PromptMessage]:
    text = text.strip()
    if not text:
        raise WorksheetError("Pick some pages with text first.")
    tokens = estimate_tokens(text)
    if tokens > MAX_WORKSHEET_TOKENS:
        raise WorksheetError(
            f"Those pages are about {tokens:,} tokens; the limit is {MAX_WORKSHEET_TOKENS:,}. "
            "Pick fewer pages."
        )
    return [
        PromptMessage(role="system", content=EXTRACT_PROMPT),
        PromptMessage(role="user", content=f"<document>\n{text}\n</document>"),
    ]


def parse_worksheet(reply: str) -> Worksheet:
    """The model's JSON, tolerating code fences or a sentence around it."""
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end < start:
        raise WorksheetError("Couldn't read questions from that. Try again, or add them by hand.")
    try:
        worksheet = Worksheet.model_validate(json.loads(reply[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as error:
        raise WorksheetError(
            "Couldn't read questions from that. Try again, or add them by hand."
        ) from error
    return worksheet.model_copy(
        update={
            "topics": [t.strip() for t in worksheet.topics if t.strip()],
            "questions": [q for q in worksheet.questions if q.text.strip()],
        }
    )
