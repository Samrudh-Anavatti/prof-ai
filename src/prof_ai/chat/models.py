from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TurnContext(BaseModel):
    """What one model call contained and cost: estimated layer sizes against reported usage."""

    layers: dict[str, int]
    estimated_input: int
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0


Author = Literal["student", "tutor"]
SupportLevel = Literal["step_by_step", "balanced", "stretch"]
Verdict = Literal["correct", "show_working", "slip", "not_yet"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime
    # Who wrote a human message, from the signed-in user. None on messages from before shared
    # chats, which were always written by the chat's owner.
    author: Author | None = None
    author_name: str | None = None
    context: TurnContext | None = None
    # The lesson question this message is about, by its number.
    question: str | None = None
    # A "Check my answer" exchange, not a request for help.
    checks_answer: bool = False


class PromptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Flag(BaseModel):
    kind: Literal["content_filter"]
    message: str
    at: datetime


class LessonSource(BaseModel):
    filename: str = Field(max_length=200)
    pages: list[int] = Field(default=[], max_length=500)


class WorkedExample(BaseModel):
    title: str = Field(default="", max_length=200)
    text: str = Field(max_length=20_000)


class Question(BaseModel):
    number: str = Field(max_length=20)
    text: str = Field(max_length=4_000)
    # The final answer, for checking a student's working. Never in the lesson layer and never
    # sent to a student's browser (R4).
    answer: str | None = Field(default=None, max_length=1_000)
    # Worked out by Prof AI and not yet confirmed by the tutor; a lesson can't be saved with it.
    answer_needs_review: bool = False
    # The first line of working a student sees at step by step, to carry on from. Never the answer.
    first_step: str | None = Field(default=None, max_length=300)
    # Drafted by Prof AI and not yet confirmed by the tutor; a lesson can't be saved with it.
    first_step_needs_review: bool = False


class Lesson(BaseModel):
    """What a tutor sets up for one chat. Rendered, it's the capped lesson layer (ADR 0005)."""

    model_config = ConfigDict(extra="ignore")

    title: str
    topics: list[str] = []
    notes: str = ""
    material: str = ""
    sources: list[LessonSource] = Field(default=[], max_length=20)
    support: SupportLevel = "balanced"
    worked_examples: list[WorkedExample] = Field(default=[], max_length=10)
    questions: list[Question] = Field(default=[], max_length=60)


class Attempt(BaseModel):
    question: str
    working: list[str] = []
    answer: str
    correct: bool
    # None for attempts from before working was marked.
    verdict: Verdict | None = None
    # False when there was no answer key to mark against.
    verified: bool = True
    at: datetime


class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    title: str = ""
    lesson: Lesson | None = None
    # A model profile's deployment; None means the default (or a tutor's preferred model).
    model: str | None = None
    created_by: str | None = None
    messages: list[ChatMessage] = []
    summary: str = ""
    summarised_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    flags: list[Flag] = []
    attempts: list[Attempt] = []
    created_at: datetime
    updated_at: datetime


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens
