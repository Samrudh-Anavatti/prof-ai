import json
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from prof_ai.auth import CurrentUser, require_role
from prof_ai.chat.models import ChatMessage, Conversation
from prof_ai.chat.service import (
    ChatEvent,
    ChatRefusedError,
    ChatService,
    ConversationNotFoundError,
    author_of,
)
from prof_ai.users.models import Role, User

Tutor = Annotated[User, Depends(require_role(Role.TUTOR))]


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    author: Literal["student", "tutor", "ai"]
    author_name: str
    content: str
    at: datetime


class LessonOverview(BaseModel):
    """What a student may see of the lesson: never the material or the tutor's notes."""

    title: str
    topics: list[str]


class ConversationDetail(ConversationSummary):
    lesson: LessonOverview | None
    messages: list[MessageOut]


class ConversationVersion(BaseModel):
    updated_at: datetime


class NewMessage(BaseModel):
    content: str
    # In a lesson chat, a student's message skips Prof AI and is only for their tutor.
    to_tutor: bool = False


def summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id, title=conversation.title, updated_at=conversation.updated_at
    )


def message_out(message: ChatMessage, owner: User) -> MessageOut:
    if message.role == "assistant":
        return MessageOut(
            role="assistant",
            author="ai",
            author_name="Prof AI",
            content=message.content,
            at=message.at,
        )
    # Messages from before shared chats have no author: the owner wrote them.
    return MessageOut(
        role="user",
        author=message.author or author_of(owner),
        author_name=message.author_name or owner.display_name,
        content=message.content,
        at=message.at,
    )


def chat_service(request: Request) -> ChatService:
    service: ChatService | None = request.app.state.chat_service
    if service is None:
        raise HTTPException(503, "Chat is not configured.")
    return service


def server_sent_events(events: Iterator[ChatEvent]) -> Iterator[str]:
    for event in events:
        yield f"event: {event.kind}\ndata: {json.dumps(event.data)}\n\n"


def conversation_detail(request: Request, owner: User, conversation_id: str) -> ConversationDetail:
    try:
        conversation = chat_service(request).get_conversation(owner, conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(404, "Chat not found.") from error
    return ConversationDetail(
        **summary(conversation).model_dump(),
        lesson=LessonOverview(title=lesson.title, topics=lesson.topics)
        if (lesson := conversation.lesson)
        else None,
        messages=[message_out(m, owner) for m in conversation.messages],
    )


def conversation_version(
    request: Request, owner: User, conversation_id: str
) -> ConversationVersion:
    try:
        updated_at = chat_service(request).conversation_version(owner, conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(404, "Chat not found.") from error
    return ConversationVersion(updated_at=updated_at)


def send_message(
    request: Request, sender: User, owner: User, conversation_id: str, message: NewMessage
) -> StreamingResponse:
    """Server-sent events: deltas if Prof AI replies, then done {title, ai} or error."""
    service = chat_service(request)
    try:
        turn = service.begin_turn(sender, owner, conversation_id, message.content, message.to_tutor)
    except ConversationNotFoundError as error:
        raise HTTPException(404, "Chat not found.") from error
    except ChatRefusedError as error:
        raise HTTPException(error.status_code, error.message) from error
    return StreamingResponse(
        server_sent_events(service.run_turn(turn)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def create_chat_router() -> APIRouter:
    router = APIRouter(prefix="/chat")

    @router.get("/conversations")
    def list_conversations(user: CurrentUser, request: Request) -> list[ConversationSummary]:
        return [summary(c) for c in chat_service(request).list_conversations(user)]

    @router.post("/conversations", status_code=201)
    def start_conversation(tutor: Tutor, request: Request) -> ConversationSummary:
        """A tutor's own test chat. Students' chats are set up under /api/students."""
        try:
            conversation = chat_service(request).create_chat(tutor, tutor)
        except ChatRefusedError as error:
            raise HTTPException(error.status_code, error.message) from error
        return summary(conversation)

    @router.get("/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: str, user: CurrentUser, request: Request
    ) -> ConversationDetail:
        return conversation_detail(request, user, conversation_id)

    @router.get("/conversations/{conversation_id}/version")
    def get_version(
        conversation_id: str, user: CurrentUser, request: Request
    ) -> ConversationVersion:
        return conversation_version(request, user, conversation_id)

    @router.post("/conversations/{conversation_id}/messages")
    def post_message(
        conversation_id: str, body: NewMessage, user: CurrentUser, request: Request
    ) -> StreamingResponse:
        return send_message(request, user, user, conversation_id, body)

    return router
