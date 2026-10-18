from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from prof_ai.auth import require_role
from prof_ai.users.admin import UserAdmin, UserAdminError
from prof_ai.users.models import AccountStatus, Role, User
from prof_ai.users.repository import UserRepository

Tutor = Annotated[User, Depends(require_role(Role.TUTOR))]


class UserView(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    status: AccountStatus
    is_admin: bool
    tutor_email: str | None
    created_at: datetime


class NewUser(BaseModel):
    email: str
    display_name: str
    role: Role = Role.STUDENT
    tutor_email: str | None = None


class LockRequest(BaseModel):
    reason: str


class UnlockRequest(BaseModel):
    reason: str = ""


def can_manage(actor: User, target: User) -> bool:
    if target.id == actor.id:
        return False
    if actor.is_admin:
        return True
    return target.role == Role.STUDENT and target.tutor_id == actor.id


def visible_users(actor: User, users: list[User]) -> list[User]:
    return [u for u in users if u.id == actor.id or can_manage(actor, u)]


def user_admin(request: Request, actor: User) -> UserAdmin:
    erase: Callable[[str], None] | None = request.app.state.erase_user_data
    if erase is None:
        raise HTTPException(503, "User management is not configured.")
    return UserAdmin(request.app.state.user_repository, None, actor.email, erase)


def views(users: list[User], everyone: list[User]) -> list[UserView]:
    emails = {u.id: u.email for u in everyone}
    return [
        UserView(
            **u.model_dump(include=set(UserView.model_fields) - {"tutor_email"}),
            tutor_email=emails.get(u.tutor_id) if u.tutor_id else None,
        )
        for u in users
    ]


def create_users_router() -> APIRouter:
    router = APIRouter(prefix="/users")

    def everyone(request: Request) -> list[User]:
        repository: UserRepository = request.app.state.user_repository
        try:
            return repository.list()
        except Exception as error:
            raise HTTPException(503, "User store is unavailable.") from error

    def managed_target(request: Request, actor: User, user_id: str) -> User:
        target = next((u for u in everyone(request) if u.id == user_id), None)
        if target is not None and target.id == actor.id:
            raise HTTPException(403, "You can't change your own account here.")
        if target is None or not can_manage(actor, target):
            raise HTTPException(404, "User not found.")
        return target

    def run(action: Callable[[], User]) -> User:
        try:
            return action()
        except UserAdminError as error:
            raise HTTPException(400, str(error)) from error
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(503, "Couldn't update the account. Try again later.") from error

    @router.get("")
    def list_users(actor: Tutor, request: Request) -> list[UserView]:
        users = everyone(request)
        return views(visible_users(actor, users), users)

    @router.post("", status_code=201)
    def invite_user(body: NewUser, actor: Tutor, request: Request) -> UserView:
        if not actor.is_admin and body.role != Role.STUDENT:
            raise HTTPException(403, "Only admins can invite tutors.")
        tutor_email = None
        if body.role == Role.STUDENT:
            tutor_email = (body.tutor_email if actor.is_admin else None) or actor.email
        admin = user_admin(request, actor)
        user = run(lambda: admin.add(body.email, body.display_name, body.role, tutor_email))
        return views([user], everyone(request))[0]

    @router.post("/{user_id}/lock")
    def lock_user(user_id: str, body: LockRequest, actor: Tutor, request: Request) -> UserView:
        target = managed_target(request, actor, user_id)
        admin = user_admin(request, actor)
        user = run(lambda: admin.lock(target.email, body.reason))
        return views([user], everyone(request))[0]

    @router.post("/{user_id}/unlock")
    def unlock_user(user_id: str, body: UnlockRequest, actor: Tutor, request: Request) -> UserView:
        target = managed_target(request, actor, user_id)
        admin = user_admin(request, actor)
        user = run(lambda: admin.unlock(target.email, body.reason))
        return views([user], everyone(request))[0]

    @router.delete("/{user_id}", status_code=204)
    def delete_user(user_id: str, actor: Tutor, request: Request) -> Response:
        target = managed_target(request, actor, user_id)
        admin = user_admin(request, actor)
        run(lambda: admin.remove(target.email))
        return Response(status_code=204)

    return router
