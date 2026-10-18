import base64
import json
from datetime import UTC, datetime

import pytest

from prof_ai.users.admin import UserAdmin
from prof_ai.users.models import AccountStatus, AuditEvent, Role, User

FIXED_NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.events: list[AuditEvent] = []
        self.fail = False

    def get(self, user_id: str) -> User | None:
        if self.fail:
            raise ConnectionError("store down")
        return self.users.get(user_id)

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def list(self) -> list[User]:
        return sorted(self.users.values(), key=lambda u: u.email)

    def save(self, user: User) -> None:
        self.users[user.id] = user

    def delete(self, user_id: str) -> None:
        self.users.pop(user_id, None)

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class FakeDirectory:
    """External ID accounts, as created by people signing up themselves."""

    def __init__(self) -> None:
        self.accounts: dict[str, dict] = {}

    def sign_up(self, user_id: str, email: str) -> None:
        self.accounts[user_id] = {"email": email, "enabled": True}

    def set_enabled(self, user_id: str, enabled: bool) -> None:
        self.accounts[user_id]["enabled"] = enabled

    def delete_user(self, user_id: str) -> None:
        del self.accounts[user_id]


def make_user(user_id="oid-1", role=Role.STUDENT, status=AccountStatus.ACTIVE, **fields) -> User:
    return User(
        id=user_id,
        email=fields.pop("email", f"{user_id}@example.com"),
        display_name=fields.pop("display_name", "Alex"),
        role=role,
        status=status,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
        **fields,
    )


def principal_header(object_id: str, email: str | None = None) -> str:
    claims = [{"typ": OBJECT_ID_CLAIM, "val": object_id}]
    if email:
        claims.append({"typ": EMAIL_CLAIM, "val": email})
    principal = {"auth_typ": "aad", "claims": claims}
    return base64.b64encode(json.dumps(principal).encode()).decode()


@pytest.fixture
def repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def directory() -> FakeDirectory:
    return FakeDirectory()


@pytest.fixture
def erased() -> list[str]:
    return []


@pytest.fixture
def admin(repository, directory, erased) -> UserAdmin:
    return UserAdmin(
        repository, directory, "sam@example.com", erased.append, clock=lambda: FIXED_NOW
    )
