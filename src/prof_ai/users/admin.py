import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from prof_ai.users.directory import Directory
from prof_ai.users.models import AccountStatus, AuditEvent, Role, User
from prof_ai.users.repository import UserRepository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserAdminError(Exception):
    pass


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise UserAdminError(f"Invalid email address: {email!r}")
    return email


class UserAdmin:
    def __init__(
        self,
        repository: UserRepository,
        directory: Directory,
        actor: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._repository = repository
        self._directory = directory
        self._actor = actor
        self._clock = clock

    def add(
        self, email: str, display_name: str, role: Role, tutor_email: str | None = None
    ) -> User:
        email = normalise_email(email)
        if not display_name.strip():
            raise UserAdminError("Display name is required.")
        if self._repository.find_by_email(email):
            raise UserAdminError(f"{email} already exists.")
        tutor_id = self._resolve_tutor(role, tutor_email)

        # Reuse a directory account left over from an earlier, interrupted add.
        user_id = self._directory.find_user_id(email) or self._directory.create_user(
            email, display_name
        )
        now = self._clock()
        user = User(
            id=user_id,
            email=email,
            display_name=display_name.strip(),
            role=role,
            tutor_id=tutor_id,
            created_at=now,
            updated_at=now,
        )
        self._repository.save(user)
        self._record(user, "user_added")
        return user

    def list(self) -> list[User]:
        return self._repository.list()

    def lock(self, email: str, reason: str) -> User:
        if not reason.strip():
            raise UserAdminError("A reason is required to lock an account.")
        user = self._require(email)
        # The app-side status is what every request checks, so it changes first.
        user = self._set_status(user, AccountStatus.ACCOUNT_LOCKED)
        self._directory.set_enabled(user.id, False)
        self._record(user, "account_locked", reason)
        return user

    def unlock(self, email: str, reason: str = "") -> User:
        user = self._require(email)
        # Re-enable sign-in before the app status, so a failure leaves the user blocked.
        self._directory.set_enabled(user.id, True)
        user = self._set_status(user, AccountStatus.ACTIVE)
        self._record(user, "account_unlocked", reason)
        return user

    def _resolve_tutor(self, role: Role, tutor_email: str | None) -> str | None:
        if role == Role.TUTOR:
            if tutor_email:
                raise UserAdminError("Only students have a tutor.")
            return None
        if not tutor_email:
            raise UserAdminError("Students need a tutor (--tutor <email>).")
        tutor = self._repository.find_by_email(normalise_email(tutor_email))
        if not tutor or tutor.role != Role.TUTOR:
            raise UserAdminError(f"No tutor with email {tutor_email}.")
        return tutor.id

    def _require(self, email: str) -> User:
        user = self._repository.find_by_email(normalise_email(email))
        if not user:
            raise UserAdminError(f"No user with email {email}.")
        return user

    def _set_status(self, user: User, status: AccountStatus) -> User:
        user = user.model_copy(update={"status": status, "updated_at": self._clock()})
        self._repository.save(user)
        return user

    def _record(self, user: User, action: str, reason: str = "") -> None:
        self._repository.record(
            AuditEvent(
                id=str(uuid.uuid4()),
                user_id=user.id,
                action=action,
                actor=self._actor,
                reason=reason,
                at=self._clock(),
            )
        )
