import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from prof_ai.users.directory import Directory
from prof_ai.users.models import AccountStatus, AuditEvent, Role, User
from prof_ai.users.repository import UserRepository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVITE_ID_PREFIX = "invite-"
SIGN_UP_INSTRUCTIONS = (
    "Ask them to open https://prof-ai.azurewebsites.net, choose to create an account "
    "with this email address, and enter the code that's emailed to them."
)

Clock = Callable[[], datetime]


class UserAdminError(Exception):
    pass


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise UserAdminError(f"Invalid email address: {email!r}")
    return email


def is_invite(user: User) -> bool:
    return user.status == AccountStatus.INVITED


def accept_invite(
    repository: UserRepository,
    user_id: str,
    email: str,
    clock: Clock = lambda: datetime.now(UTC),
) -> User | None:
    """Links a pending invite to the identity that just signed in with the invited email."""
    invite = repository.find_by_email(email.strip().lower())
    if invite is None or not is_invite(invite):
        return None
    now = clock()
    user = invite.model_copy(
        update={"id": user_id, "status": AccountStatus.ACTIVE, "updated_at": now}
    )
    repository.save(user)
    repository.delete(invite.id)
    repository.record(
        AuditEvent(
            id=str(uuid.uuid4()),
            user_id=user.id,
            action="invite_accepted",
            actor=user.email,
            at=now,
        )
    )
    return user


class UserAdmin:
    def __init__(
        self,
        repository: UserRepository,
        directory: Directory | None,
        actor: str,
        erase_user_data: Callable[[str], None],
        clock: Clock = lambda: datetime.now(UTC),
    ):
        self._repository = repository
        self._directory = directory
        self._actor = actor
        self._erase_user_data = erase_user_data
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
        now = self._clock()
        user = User(
            id=f"{INVITE_ID_PREFIX}{uuid.uuid4()}",
            email=email,
            display_name=display_name.strip(),
            role=role,
            status=AccountStatus.INVITED,
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
        if is_invite(user):
            raise UserAdminError(f"{user.email} hasn't signed up yet. Delete the invite instead.")
        # The app-side status is what every request checks, so it changes first.
        user = self._set_status(user, AccountStatus.ACCOUNT_LOCKED)
        if self._directory:
            self._directory.set_enabled(user.id, False)
        self._record(user, "account_locked", reason)
        return user

    def unlock(self, email: str, reason: str = "") -> User:
        user = self._require(email)
        if user.status != AccountStatus.ACCOUNT_LOCKED:
            raise UserAdminError(f"{user.email} isn't locked.")
        # Re-enable sign-in before the app status, so a failure leaves the user blocked.
        if self._directory:
            self._directory.set_enabled(user.id, True)
        user = self._set_status(user, AccountStatus.ACTIVE)
        self._record(user, "account_unlocked", reason)
        return user

    def remove(self, email: str) -> User:
        user = self._require(email)
        if user.role == Role.TUTOR and any(u.tutor_id == user.id for u in self._repository.list()):
            raise UserAdminError(f"{user.email} still has students. Remove them first.")
        # Data before the record, so a failure part-way can be retried from the same email.
        self._erase_user_data(user.id)
        self._repository.delete(user.id)
        if self._directory and not is_invite(user):
            self._directory.delete_user(user.id)
        self._record(user, "user_removed", user.email)
        return user

    def set_admin(self, email: str, is_admin: bool) -> User:
        user = self._require(email)
        if is_admin and user.role != Role.TUTOR:
            raise UserAdminError("Only tutors can be admins.")
        user = user.model_copy(update={"is_admin": is_admin, "updated_at": self._clock()})
        self._repository.save(user)
        self._record(user, "admin_granted" if is_admin else "admin_revoked")
        return user

    def _resolve_tutor(self, role: Role, tutor_email: str | None) -> str | None:
        if role == Role.TUTOR:
            if tutor_email:
                raise UserAdminError("Only students have a tutor.")
            return None
        if not tutor_email:
            raise UserAdminError("Students need a tutor.")
        tutor = self._repository.find_by_email(normalise_email(tutor_email))
        if not tutor or tutor.role != Role.TUTOR:
            raise UserAdminError(f"No tutor with email {tutor_email}.")
        if is_invite(tutor):
            raise UserAdminError(f"{tutor.email} hasn't signed up yet, so can't have students.")
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
