import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from prof_ai.auth import require_role
from prof_ai.chat.prompts import build_system_prompt
from prof_ai.profiles.store import (
    MAX_PROFILE_BYTES,
    InvalidProfileError,
    ProfileFile,
    ProfileStore,
)
from prof_ai.users.models import AuditEvent, Role, User
from prof_ai.users.repository import UserRepository

Tutor = Annotated[User, Depends(require_role(Role.TUTOR))]


class TeachingStyle(BaseModel):
    content: str
    system_prompt: str
    max_bytes: int = MAX_PROFILE_BYTES


class TeachingStyleUpdate(BaseModel):
    content: str


def profile_store(request: Request) -> ProfileStore:
    store: ProfileStore | None = request.app.state.profile_store
    if store is None:
        raise HTTPException(503, "Profiles are not configured.")
    return store


def teaching_style(tutor: User, store: ProfileStore) -> TeachingStyle:
    try:
        return TeachingStyle(
            content=store.get(tutor.id, ProfileFile.TEACHING_STYLE) or "",
            system_prompt=build_system_prompt(tutor, store),
        )
    except Exception as error:
        raise HTTPException(503, "Profiles are unavailable. Try again later.") from error


def create_profiles_router() -> APIRouter:
    router = APIRouter(prefix="/teaching-style")

    @router.get("")
    def get_teaching_style(tutor: Tutor, request: Request) -> TeachingStyle:
        return teaching_style(tutor, profile_store(request))

    @router.put("")
    def save_teaching_style(
        body: TeachingStyleUpdate, tutor: Tutor, request: Request
    ) -> TeachingStyle:
        store = profile_store(request)
        try:
            store.put(tutor.id, ProfileFile.TEACHING_STYLE, body.content)
        except InvalidProfileError as error:
            raise HTTPException(400, str(error)) from error
        except Exception as error:
            raise HTTPException(503, "Couldn't save. Try again later.") from error
        users: UserRepository = request.app.state.user_repository
        users.record(
            AuditEvent(
                id=str(uuid.uuid4()),
                user_id=tutor.id,
                action="teaching_style_updated",
                actor=tutor.email,
                at=datetime.now(UTC),
            )
        )
        return teaching_style(tutor, store)

    return router
