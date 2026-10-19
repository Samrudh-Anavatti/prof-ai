from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TurnContext(BaseModel):
    """What one model call contained and cost: estimated layer sizes against reported usage."""

    layers: dict[str, int]
    estimated_input: int
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime
    context: TurnContext | None = None


class PromptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Flag(BaseModel):
    kind: Literal["content_filter"]
    message: str
    at: datetime


class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    title: str = ""
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
