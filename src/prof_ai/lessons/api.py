import base64
import binascii
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from prof_ai.auth import require_role
from prof_ai.chat.api import (
    ConversationDetail,
    ConversationVersion,
    NewMessage,
    chat_service,
    conversation_detail,
    conversation_version,
    send_message,
)
from prof_ai.chat.context import LAYER_CAPS, Layer
from prof_ai.chat.models import Conversation, Lesson, SupportLevel
from prof_ai.chat.service import (
    MAX_CHATS_PER_STUDENT,
    ChatRefusedError,
    ConversationNotFoundError,
)
from prof_ai.lessons.pdf_text import MAX_LESSON_PDF_BYTES, LessonPdfError, extract_pages
from prof_ai.users.api import can_manage
from prof_ai.users.models import AuditEvent, Role, User
from prof_ai.users.repository import UserRepository

Tutor = Annotated[User, Depends(require_role(Role.TUTOR))]
# Base64 adds a third; allow some room for the JSON around it.
MAX_EXTRACT_REQUEST_BYTES = MAX_LESSON_PDF_BYTES * 4 // 3 + 64 * 1024


class StudentChat(BaseModel):
    id: str
    title: str
    topics: list[str]
    has_material: bool
    support: SupportLevel | None
    # None: the default model.
    model: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class StudentChats(BaseModel):
    chats: list[StudentChat]
    max_chats: int = MAX_CHATS_PER_STUDENT
    max_lesson_tokens: int = LAYER_CAPS[Layer.LESSON]


class NewLessonChat(BaseModel):
    lesson: Lesson
    licence_confirmed: bool = False
    model: str | None = None


class ChatChange(BaseModel):
    support: SupportLevel | None = None
    model: str | None = None


class PdfUpload(BaseModel):
    filename: str
    pdf_base64: str


class ExtractedPage(BaseModel):
    number: int
    text: str
    tokens: int


class ExtractedPdf(BaseModel):
    pages: list[ExtractedPage]
    max_lesson_tokens: int = LAYER_CAPS[Layer.LESSON]


def student_chat(conversation: Conversation) -> StudentChat:
    lesson = conversation.lesson
    return StudentChat(
        id=conversation.id,
        title=conversation.title or "(untitled)",
        topics=lesson.topics if lesson else [],
        has_material=bool(lesson and lesson.material),
        support=lesson.support if lesson else None,
        model=conversation.model,
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def managed_student(request: Request, actor: User, student_id: str) -> User:
    """The student, if this tutor may set up their chats. Anyone else's is a plain 404."""
    users: UserRepository = request.app.state.user_repository
    try:
        student = users.get(student_id)
    except Exception as error:
        raise HTTPException(503, "User store is unavailable.") from error
    if student is None:
        raise HTTPException(404, "Student not found.")
    is_self = student.id == actor.id
    if not is_self and not (student.role == Role.STUDENT and can_manage(actor, student)):
        raise HTTPException(404, "Student not found.")
    return student


def audit(request: Request, actor: User, student: User, action: str, reason: str) -> None:
    users: UserRepository = request.app.state.user_repository
    users.record(
        AuditEvent(
            id=str(uuid.uuid4()),
            user_id=student.id,
            action=action,
            actor=actor.email,
            reason=reason,
            at=datetime.now(UTC),
        )
    )


def create_lessons_router() -> APIRouter:
    router = APIRouter()

    @router.get("/students/{student_id}/chats")
    def list_student_chats(student_id: str, tutor: Tutor, request: Request) -> StudentChats:
        student = managed_student(request, tutor, student_id)
        try:
            chats = chat_service(request).list_conversations(student)
        except Exception as error:
            raise HTTPException(503, "Chats are unavailable. Try again later.") from error
        return StudentChats(chats=[student_chat(c) for c in chats])

    @router.post("/students/{student_id}/chats", status_code=201)
    def create_student_chat(
        student_id: str, body: NewLessonChat, tutor: Tutor, request: Request
    ) -> StudentChat:
        student = managed_student(request, tutor, student_id)
        try:
            conversation = chat_service(request).create_chat(
                tutor, student, body.lesson, body.licence_confirmed, body.model
            )
        except ChatRefusedError as error:
            raise HTTPException(error.status_code, error.message) from error
        except Exception as error:
            raise HTTPException(503, "Couldn't create the chat. Try again later.") from error
        audit(request, tutor, student, "chat_created", conversation.title)
        return student_chat(conversation)

    @router.get("/students/{student_id}/chats/{conversation_id}")
    def get_student_chat(
        student_id: str, conversation_id: str, tutor: Tutor, request: Request
    ) -> ConversationDetail:
        student = managed_student(request, tutor, student_id)
        return conversation_detail(request, student, conversation_id)

    @router.get("/students/{student_id}/chats/{conversation_id}/version")
    def get_student_chat_version(
        student_id: str, conversation_id: str, tutor: Tutor, request: Request
    ) -> ConversationVersion:
        student = managed_student(request, tutor, student_id)
        return conversation_version(request, student, conversation_id)

    @router.post("/students/{student_id}/chats/{conversation_id}/messages")
    def post_student_chat_message(
        student_id: str, conversation_id: str, body: NewMessage, tutor: Tutor, request: Request
    ) -> StreamingResponse:
        """The tutor writes in their student's chat; @AI asks Prof AI, charged to the tutor."""
        student = managed_student(request, tutor, student_id)
        return send_message(request, tutor, student, conversation_id, body)

    @router.patch("/students/{student_id}/chats/{conversation_id}")
    def change_student_chat(
        student_id: str, conversation_id: str, body: ChatChange, tutor: Tutor, request: Request
    ) -> StudentChat:
        """Change a chat's support level, its model, or both."""
        student = managed_student(request, tutor, student_id)
        if body.support is None and body.model is None:
            raise HTTPException(400, "Nothing to change.")
        service = chat_service(request)
        try:
            if body.model is not None:
                conversation = service.set_model(student, conversation_id, body.model)
                audit(
                    request,
                    tutor,
                    student,
                    "chat_model_changed",
                    f"{conversation.title}: {body.model}",
                )
            if body.support is not None:
                conversation = service.set_support(student.id, conversation_id, body.support)
                audit(
                    request,
                    tutor,
                    student,
                    "chat_support_changed",
                    f"{conversation.title}: {body.support}",
                )
        except ConversationNotFoundError as error:
            raise HTTPException(404, "Chat not found.") from error
        except ChatRefusedError as error:
            raise HTTPException(error.status_code, error.message) from error
        except Exception as error:
            raise HTTPException(503, "Couldn't change the chat. Try again later.") from error
        return student_chat(conversation)

    @router.delete("/students/{student_id}/chats/{conversation_id}", status_code=204)
    def delete_student_chat(
        student_id: str, conversation_id: str, tutor: Tutor, request: Request
    ) -> Response:
        student = managed_student(request, tutor, student_id)
        try:
            conversation = chat_service(request).delete_chat(student.id, conversation_id)
        except ConversationNotFoundError as error:
            raise HTTPException(404, "Chat not found.") from error
        except Exception as error:
            raise HTTPException(503, "Couldn't delete the chat. Try again later.") from error
        audit(request, tutor, student, "chat_deleted", conversation.title)
        return Response(status_code=204)

    @router.post("/lessons/extract")
    def extract_pdf(body: PdfUpload, tutor: Tutor) -> ExtractedPdf:
        try:
            data = base64.b64decode(body.pdf_base64, validate=True)
            pages = extract_pages(data)
        except LessonPdfError as error:
            raise HTTPException(400, str(error)) from error
        except binascii.Error as error:
            raise HTTPException(400, "That file isn't a PDF.") from error
        return ExtractedPdf(pages=[ExtractedPage(**vars(page)) for page in pages])

    return router
