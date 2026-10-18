import pytest
from fastapi.testclient import TestClient

from prof_ai.auth import PRINCIPAL_HEADER, principal_object_id
from prof_ai.config import Settings, UnsafeConfigError
from prof_ai.main import create_app
from prof_ai.users.models import AccountStatus, Role

from .conftest import make_user, principal_header

PRODUCTION = Settings(app_env="production", on_app_service=True, platform_auth_enabled=True)


def client(repository, settings=PRODUCTION) -> TestClient:
    return TestClient(create_app(settings, user_repository=repository))


def test_principal_object_id_reads_easy_auth_header():
    assert principal_object_id(principal_header("abc-123")) == "abc-123"


@pytest.mark.parametrize("value", ["not-base64!!", "e30=", "bnVsbA=="])
def test_principal_object_id_rejects_malformed_headers(value):
    assert principal_object_id(value) is None


def test_me_returns_the_signed_in_user(repository):
    repository.save(make_user("oid-1", role=Role.TUTOR, email="sam@example.com"))
    response = client(repository).get("/me", headers={PRINCIPAL_HEADER: principal_header("oid-1")})
    assert response.status_code == 200
    assert response.json() == {
        "id": "oid-1",
        "email": "sam@example.com",
        "display_name": "Alex",
        "role": "tutor",
        "status": "active",
    }


def test_missing_principal_is_unauthorised(repository):
    assert client(repository).get("/me").status_code == 401


def test_principal_header_ignored_when_platform_auth_is_off_in_production(repository):
    repository.save(make_user("oid-1"))
    settings = Settings(app_env="production", on_app_service=True, platform_auth_enabled=False)
    response = client(repository, settings).get(
        "/me", headers={PRINCIPAL_HEADER: principal_header("oid-1")}
    )
    assert response.status_code == 401


def test_uninvited_identity_is_forbidden(repository):
    response = client(repository).get(
        "/me", headers={PRINCIPAL_HEADER: principal_header("stranger")}
    )
    assert response.status_code == 403
    assert "invited" in response.json()["detail"]


def test_locked_account_is_forbidden(repository):
    repository.save(make_user("oid-1", status=AccountStatus.ACCOUNT_LOCKED))
    response = client(repository).get("/me", headers={PRINCIPAL_HEADER: principal_header("oid-1")})
    assert response.status_code == 403
    assert "locked" in response.json()["detail"]


def test_user_store_failure_fails_closed(repository):
    repository.save(make_user("oid-1"))
    repository.fail = True
    response = client(repository).get("/me", headers={PRINCIPAL_HEADER: principal_header("oid-1")})
    assert response.status_code == 503


def test_healthz_needs_no_sign_in(repository):
    assert client(repository).get("/healthz").status_code == 200


def test_dev_user_works_locally(repository):
    repository.save(make_user("oid-dev"))
    settings = Settings(app_env="local", dev_user_id="oid-dev")
    assert client(repository, settings).get("/me").json()["id"] == "oid-dev"


@pytest.mark.parametrize(
    "settings",
    [
        Settings(app_env="production", dev_user_id="oid-dev"),
        Settings(app_env="local", dev_user_id="oid-dev", on_app_service=True),
    ],
)
def test_dev_user_refused_outside_local(settings):
    with pytest.raises(UnsafeConfigError):
        create_app(settings)
