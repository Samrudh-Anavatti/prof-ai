import base64
import json
from datetime import UTC, datetime

import pytest

from prof_ai.users.admin import UserAdmin
from prof_ai.users.models import AccountStatus, AuditEvent, Role, User

FIXED_NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"


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

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class FakeDirectory:
    def __init__(self) -> None:
        self.accounts: dict[str, dict] = {}

    def find_user_id(self, email: str) -> str | None:
        return next((i for i, a in self.accounts.items() if a["email"] == email), None)

    def create_user(self, email: str, display_name: str) -> str:
        user_id = f"oid-{len(self.accounts) + 1}"
        self.accounts[user_id] = {"email": email, "name": display_name, "enabled": True}
        return user_id

    def set_enabled(self, user_id: str, enabled: bool) -> None:
        self.accounts[user_id]["enabled"] = enabled


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


def principal_header(object_id: str) -> str:
    principal = {"auth_typ": "aad", "claims": [{"typ": OBJECT_ID_CLAIM, "val": object_id}]}
    return base64.b64encode(json.dumps(principal).encode()).decode()


@pytest.fixture
def repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def directory() -> FakeDirectory:
    return FakeDirectory()


@pytest.fixture
def admin(repository, directory) -> UserAdmin:
    return UserAdmin(repository, directory, actor="sam@example.com", clock=lambda: FIXED_NOW)
