import json
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from prof_ai.auth import CurrentUser
from prof_ai.chat.models import ChatMessage, Conversation
from prof_ai.chat.service import (
    ChatEvent,
    ChatRefusedError,
    ChatService,
    ConversationNotFoundError,
)


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessage]


class NewMessage(BaseModel):
    content: str


def summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id, title=conversation.title, updated_at=conversation.updated_at
    )


def chat_service(request: Request) -> ChatService:
    service: ChatService | None = request.app.state.chat_service
    if service is None:
        raise HTTPException(503, "Chat is not configured.")
    return service


def server_sent_events(events: Iterator[ChatEvent]) -> Iterator[str]:
    for event in events:
        yield f"event: {event.kind}\ndata: {json.dumps(event.data)}\n\n"


def create_chat_router() -> APIRouter:
    router = APIRouter(prefix="/chat")

    @router.get("/conversations")
    def list_conversations(user: CurrentUser, request: Request) -> list[ConversationSummary]:
        return [summary(c) for c in chat_service(request).list_conversations(user)]

    @router.post("/conversations", status_code=201)
    def start_conversation(user: CurrentUser, request: Request) -> ConversationSummary:
        return summary(chat_service(request).start_conversation(user))

    @router.get("/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: str, user: CurrentUser, request: Request
    ) -> ConversationDetail:
        try:
            conversation = chat_service(request).get_conversation(user, conversation_id)
        except ConversationNotFoundError as error:
            raise HTTPException(404, "Chat not found.") from error
        return ConversationDetail(
            **summary(conversation).model_dump(), messages=conversation.messages
        )

    @router.post("/conversations/{conversation_id}/messages")
    def send_message(
        conversation_id: str, body: NewMessage, user: CurrentUser, request: Request
    ) -> StreamingResponse:
        service = chat_service(request)
        try:
            turn = service.begin_turn(user, conversation_id, body.content)
        except ConversationNotFoundError as error:
            raise HTTPException(404, "Chat not found.") from error
        except ChatRefusedError as error:
            raise HTTPException(error.status_code, error.message) from error
        return StreamingResponse(
            server_sent_events(service.run_turn(turn)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
