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


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime
    # Who wrote a human message, from the signed-in user. None on messages from before shared
    # chats, which were always written by the chat's owner.
    author: Author | None = None
    author_name: str | None = None
    context: TurnContext | None = None


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


class Lesson(BaseModel):
    """What a tutor sets up for one chat. Rendered, it's the capped lesson layer (ADR 0005)."""

    model_config = ConfigDict(extra="ignore")

    title: str
    topics: list[str] = []
    notes: str = ""
    material: str = ""
    sources: list[LessonSource] = Field(default=[], max_length=20)


class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    title: str = ""
    lesson: Lesson | None = None
    created_by: str | None = None
    messages: list[ChatMessage] = []
    summary: str = ""
    summarised_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    flags: list[Flag] = []
    created_at: datetime
    updated_at: datetime


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens
