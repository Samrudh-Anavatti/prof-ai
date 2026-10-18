from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime


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
    input_tokens: int = 0
    output_tokens: int = 0
    flags: list[Flag] = []
    created_at: datetime
    updated_at: datetime


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens
