import base64
import binascii
import json
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from prof_ai.config import Settings
from prof_ai.users.admin import accept_invite
from prof_ai.users.models import AccountStatus, Role, User
from prof_ai.users.repository import UserRepository

PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"
OBJECT_ID_CLAIMS = ("http://schemas.microsoft.com/identity/claims/objectidentifier", "oid")
EMAIL_CLAIMS = ("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "email")


def _principal_claim(header_value: str, types: tuple[str, ...]) -> str | None:
    try:
        principal = json.loads(base64.b64decode(header_value))
    except (binascii.Error, ValueError):
        return None
    claims = principal.get("claims") if isinstance(principal, dict) else None
    for claim in claims or []:
        if isinstance(claim, dict) and claim.get("typ") in types and claim.get("val"):
            return str(claim["val"])
    return None


def principal_object_id(header_value: str) -> str | None:
    return _principal_claim(header_value, OBJECT_ID_CLAIMS)


def principal_email(header_value: str) -> str | None:
    return _principal_claim(header_value, EMAIL_CLAIMS)


def _signed_in_user_id(request: Request, settings: Settings) -> str:
    if settings.dev_user_id:
        return settings.dev_user_id
    # Only App Service Authentication may set the principal header; it strips client copies.
    if settings.is_production and not settings.platform_auth_enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign-in is not configured.")
    header = request.headers.get(PRINCIPAL_HEADER)
    user_id = principal_object_id(header) if header else None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    return user_id


def current_user(request: Request) -> User:
    settings: Settings = request.app.state.settings
    repository: UserRepository | None = request.app.state.user_repository
    user_id = _signed_in_user_id(request, settings)
    if repository is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "User store is not configured.")
    try:
        user = repository.get(user_id) or _accept_invite(request, repository, user_id)
    except Exception as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "User store is unavailable."
        ) from error
    if user is None or user.status == AccountStatus.INVITED:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This account hasn't been invited. Ask your tutor."
        )
    if user.status == AccountStatus.ACCOUNT_LOCKED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is locked. Ask your tutor.")
    return user


def _accept_invite(request: Request, repository: UserRepository, user_id: str) -> User | None:
    if request.app.state.settings.dev_user_id:
        return None
    # Trusted for the same reason as the object ID: only Easy Auth can set this header.
    header = request.headers.get(PRINCIPAL_HEADER)
    email = principal_email(header) if header else None
    return accept_invite(repository, user_id, email) if email else None


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: Role) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed.")
        return user

    return dependency
