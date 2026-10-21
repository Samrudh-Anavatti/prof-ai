import json
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from prof_ai.chat.models import PromptMessage, SupportLevel
from prof_ai.lessons.rules import MAX_NOTES_CHARS, MAX_TITLE_CHARS, MAX_TOPIC_CHARS, MAX_TOPICS

DESCRIBE_PROMPT = (
    (Path(__file__).parent / "prompts" / "describe_lesson.md").read_text(encoding="utf-8").strip()
)
MAX_DESCRIPTION_CHARS = 4_000
DRAFT_OUTPUT_TOKENS = 800
# What a good description covers, in the order the Lessons page shows it (web/src/lessons.ts).
CHECKLIST = ("level", "topic", "covered", "struggles", "support", "focus")
UNREADABLE = "Couldn't draft a lesson from that. Try again, or fill the form in instead."


class DraftError(ValueError):
    pass


class LessonDraft(BaseModel):
    title: str = ""
    topics: list[str] = []
    notes: str = ""
    support: SupportLevel | None = None
    unanswered: list[str] = []


def draft_request(description: str) -> list[PromptMessage]:
    description = description.strip()
    if not description:
        raise DraftError("Describe the lesson first.")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise DraftError(f"Keep the description under {MAX_DESCRIPTION_CHARS:,} characters.")
    return [
        PromptMessage(role="system", content=DESCRIBE_PROMPT),
        PromptMessage(role="user", content=f"<description>\n{description}\n</description>"),
    ]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def parse_draft(reply: str) -> LessonDraft:
    """The model's JSON, clipped to what a lesson allows; anything unexpected is dropped."""
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        raise DraftError(UNREADABLE)
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    unanswered = data.get("unanswered") if isinstance(data.get("unanswered"), list) else []
    support = data.get("support")
    return LessonDraft(
        title=_text(data.get("title"))[:MAX_TITLE_CHARS],
        topics=[t[:MAX_TOPIC_CHARS] for t in map(_text, topics) if t][:MAX_TOPICS],
        notes=_text(data.get("notes"))[:MAX_NOTES_CHARS],
        support=support if support in get_args(SupportLevel) else None,
        unanswered=[item for item in CHECKLIST if item in unanswered],
    )
