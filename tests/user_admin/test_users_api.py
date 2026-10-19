import pytest
from fastapi.testclient import TestClient

from prof_ai.auth import PRINCIPAL_HEADER
from prof_ai.main import create_app
from prof_ai.profiles.store import ProfileFile
from prof_ai.users.models import AccountStatus
from tests.auth.conftest import principal_header
from tests.tutor_chat.conftest import FIXED_NOW, PRODUCTION, Harness

URL = "/api/users"


class AdminHarness(Harness):
    """Sam is an admin; Punjy is a tutor; Alex is Sam's student; Bea is Punjy's."""

    def __init__(self) -> None:
        super().__init__()
        sam = self.users.get("sam")
        self.users.save(sam.model_copy(update={"is_admin": True}))
        self.client = TestClient(
            create_app(
                PRODUCTION,
                user_repository=self.users,
                chat_service=self.service,
                profile_store=self.profiles,
            )
        )

    def get(self, actor: str, path: str = URL):
        return self.client.get(path, headers=self.as_user(actor))

    def invite(self, actor: str, **body):
        return self.client.post(URL, json=body, headers=self.as_user(actor))

    def lock(self, actor: str, user_id: str, reason: str = "Testing"):
        return self.client.post(
            f"{URL}/{user_id}/lock", json={"reason": reason}, headers=self.as_user(actor)
        )

    def unlock(self, actor: str, user_id: str):
        return self.client.post(f"{URL}/{user_id}/unlock", json={}, headers=self.as_user(actor))

    def delete(self, actor: str, user_id: str):
        return self.client.delete(f"{URL}/{user_id}", headers=self.as_user(actor))

    def first_sign_in(self, object_id: str, email: str):
        return self.client.get(
            "/api/me", headers={PRINCIPAL_HEADER: principal_header(object_id, email)}
        )


@pytest.fixture
def h() -> AdminHarness:
    return AdminHarness()


def emails(response) -> set[str]:
    return {u["email"] for u in response.json()}


def test_admin_sees_everyone_with_their_tutors(h):
    response = h.get("sam")

    assert response.status_code == 200
    assert emails(response) == {
        "sam@example.com",
        "punjy@example.com",
        "alex@example.com",
        "bea@example.com",
    }
    bea = next(u for u in response.json() if u["email"] == "bea@example.com")
    assert bea["tutor_email"] == "punjy@example.com"
    assert bea["status"] == "active"
    assert bea["is_admin"] is False


def test_tutor_sees_only_themselves_and_their_students(h):
    assert emails(h.get("punjy")) == {"punjy@example.com", "bea@example.com"}


def test_students_cannot_use_the_admin_api(h):
    assert h.get("alex").status_code == 403
    assert h.invite("alex", email="x@example.com", display_name="X").status_code == 403
    assert h.delete("alex", "bea").status_code == 403


def test_me_reports_admin(h):
    assert h.get("sam", "/api/me").json()["is_admin"] is True
    assert h.get("punjy", "/api/me").json()["is_admin"] is False


def test_tutor_invites_a_student_who_is_always_theirs(h):
    response = h.invite(
        "punjy", email="Cara@Example.com", display_name="Cara", tutor_email="sam@example.com"
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["status"], body["role"]) == (
        "cara@example.com",
        "invited",
        "student",
    )
    assert body["tutor_email"] == "punjy@example.com"
    assert h.users.events[-1].action == "user_added"


def test_only_admins_invite_tutors(h):
    assert (
        h.invite("punjy", email="t@example.com", display_name="T", role="tutor").status_code == 403
    )
    response = h.invite("sam", email="t@example.com", display_name="T", role="tutor")
    assert response.status_code == 201
    assert response.json()["role"] == "tutor"


def test_admin_invites_a_student_for_another_tutor(h):
    response = h.invite(
        "sam", email="cara@example.com", display_name="Cara", tutor_email="punjy@example.com"
    )

    assert response.json()["tutor_email"] == "punjy@example.com"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "alex@example.com", "display_name": "Alex again"},
        {"email": "not-an-email", "display_name": "X"},
        {"email": "x@example.com", "display_name": " "},
    ],
)
def test_invalid_invites_are_refused(h, body):
    response = h.invite("sam", **body, tutor_email="sam@example.com")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_first_sign_in_with_the_invited_email_activates_the_account(h):
    invite = h.invite("sam", email="cara@example.com", display_name="Cara").json()

    response = h.first_sign_in("oid-cara", "CARA@example.com")

    assert response.status_code == 200
    assert response.json()["id"] == "oid-cara"
    assert h.users.get("oid-cara").tutor_id == "sam"
    assert h.users.get(invite["id"]) is None
    assert h.users.events[-1].action == "invite_accepted"
    assert h.get("oid-cara", "/api/me").status_code == 200


def test_sign_in_without_a_matching_invite_is_refused(h):
    h.invite("sam", email="cara@example.com", display_name="Cara")

    assert h.first_sign_in("oid-stranger", "stranger@example.com").status_code == 403
    assert h.get("oid-stranger", "/api/me").status_code == 403
    assert h.first_sign_in("oid-alex-2", "alex@example.com").status_code == 403
    assert h.users.get("alex").status == AccountStatus.ACTIVE


def test_an_invite_cannot_be_used_by_its_own_id(h):
    invite = h.invite("sam", email="cara@example.com", display_name="Cara").json()

    assert h.get(invite["id"], "/api/me").status_code == 403


def test_lock_blocks_the_student_and_unlock_restores_them(h):
    assert h.lock("sam", "alex", reason="Spamming").json()["status"] == "account_locked"
    assert h.get("alex", "/api/me").status_code == 403
    assert h.users.events[-1].reason == "Spamming"

    assert h.unlock("sam", "alex").json()["status"] == "active"
    assert h.get("alex", "/api/me").status_code == 200


def test_lock_needs_a_reason_and_a_signed_up_user(h):
    assert h.lock("sam", "alex", reason=" ").status_code == 400
    invite = h.invite("sam", email="cara@example.com", display_name="Cara").json()
    assert h.lock("sam", invite["id"]).status_code == 400


def test_tutors_cannot_touch_other_tutors_students_or_tutors(h):
    for user_id in ("alex", "sam"):
        assert h.lock("punjy", user_id).status_code == 404
        assert h.unlock("punjy", user_id).status_code == 404
        assert h.delete("punjy", user_id).status_code == 404
    assert h.users.get("alex").status == AccountStatus.ACTIVE
    assert h.users.get("sam") is not None


def test_nobody_locks_or_deletes_themselves(h):
    assert h.lock("sam", "sam").status_code == 403
    assert h.delete("sam", "sam").status_code == 403


def test_delete_erases_chats_usage_profiles_and_the_account(h):
    h.send("bea", h.start("bea"), "hi")
    h.profiles.put("bea", ProfileFile.PROFILE, "Bea is in year 8.")
    h.send("alex", h.start("alex"), "hi")

    assert h.delete("punjy", "bea").status_code == 204

    assert h.users.get("bea") is None
    assert h.store.list_conversations("bea") == []
    assert h.store.cost_used("bea", FIXED_NOW.date()) == 0
    assert h.profiles.get("bea", ProfileFile.PROFILE) is None
    assert len(h.store.list_conversations("alex")) == 1
    assert (h.users.events[-1].action, h.users.events[-1].reason) == (
        "user_removed",
        "bea@example.com",
    )


def test_a_tutor_with_students_cannot_be_deleted(h):
    assert h.delete("sam", "punjy").status_code == 400
    assert h.delete("sam", "bea").status_code == 204
    assert h.delete("sam", "punjy").status_code == 204


def test_delete_failure_keeps_the_account(h, monkeypatch):
    def fail(user_id):
        raise ConnectionError("cosmos down")

    monkeypatch.setattr(h.store, "delete_user_data", fail)

    assert h.delete("sam", "alex").status_code == 503
    assert h.users.get("alex") is not None


@pytest.mark.parametrize("path", [URL, f"{URL}/alex/lock", f"{URL}/alex/unlock"])
def test_non_json_bodies_are_rejected(h, path):
    response = h.client.post(
        path,
        content="reason=x&email=x@example.com&display_name=X",
        headers={**h.as_user("sam"), "Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422
    assert h.users.get("alex").status == AccountStatus.ACTIVE


def test_without_stores_user_management_is_unavailable():
    harness = Harness()

    response = harness.client.post(
        URL,
        json={"email": "x@example.com", "display_name": "X"},
        headers=harness.as_user("sam"),
    )
    assert response.status_code == 503
