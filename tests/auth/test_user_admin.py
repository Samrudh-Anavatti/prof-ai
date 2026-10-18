import pytest

from prof_ai.cli import main
from prof_ai.users.admin import UserAdminError
from prof_ai.users.models import AccountStatus, Role


def add_tutor(admin, email="sam@example.com"):
    return admin.add(email, "Sam", Role.TUTOR)


def test_add_creates_directory_account_and_user(admin, repository, directory):
    tutor = add_tutor(admin, " Sam@Example.com ")
    assert tutor.email == "sam@example.com"
    assert directory.accounts[tutor.id]["email"] == "sam@example.com"
    assert repository.get(tutor.id).role == Role.TUTOR
    assert [(e.action, e.actor) for e in repository.events] == [("user_added", "sam@example.com")]


def test_student_is_linked_to_their_tutor(admin):
    tutor = add_tutor(admin)
    student = admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="sam@example.com")
    assert student.tutor_id == tutor.id
    assert student.status == AccountStatus.ACTIVE


def test_student_needs_an_existing_tutor(admin):
    with pytest.raises(UserAdminError):
        admin.add("alex@example.com", "Alex", Role.STUDENT)
    with pytest.raises(UserAdminError):
        admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="nobody@example.com")


def test_tutor_cannot_have_a_tutor(admin):
    add_tutor(admin)
    with pytest.raises(UserAdminError):
        admin.add("punjy@example.com", "Punjy", Role.TUTOR, tutor_email="sam@example.com")


def test_duplicate_email_is_refused(admin):
    add_tutor(admin)
    with pytest.raises(UserAdminError):
        add_tutor(admin, "SAM@example.com")


def test_invalid_email_is_refused(admin, directory):
    with pytest.raises(UserAdminError):
        admin.add("not-an-email", "Sam", Role.TUTOR)
    assert directory.accounts == {}


def test_add_reuses_directory_account_from_interrupted_add(admin, directory):
    existing_id = directory.create_user("sam@example.com", "Sam")
    assert add_tutor(admin).id == existing_id
    assert len(directory.accounts) == 1


def test_lock_blocks_in_app_and_directory_and_is_audited(admin, repository, directory):
    tutor = add_tutor(admin)
    admin.lock("sam@example.com", reason="Prompt injection attempt")
    assert repository.get(tutor.id).status == AccountStatus.ACCOUNT_LOCKED
    assert directory.accounts[tutor.id]["enabled"] is False
    assert (repository.events[-1].action, repository.events[-1].reason) == (
        "account_locked",
        "Prompt injection attempt",
    )


def test_lock_requires_a_reason(admin):
    add_tutor(admin)
    with pytest.raises(UserAdminError):
        admin.lock("sam@example.com", reason=" ")


def test_unlock_restores_access(admin, repository, directory):
    tutor = add_tutor(admin)
    admin.lock("sam@example.com", reason="test")
    admin.unlock("sam@example.com")
    assert repository.get(tutor.id).status == AccountStatus.ACTIVE
    assert directory.accounts[tutor.id]["enabled"] is True
    assert repository.events[-1].action == "account_unlocked"


def test_cli_users_commands(admin, capsys):
    def run(*argv):
        return main(list(argv), admin_factory=lambda: admin)

    assert (
        run("users", "add", "--email", "sam@example.com", "--name", "Sam", "--role", "tutor") == 0
    )
    assert run(
        "users", "add", "--email", "alex@example.com", "--name", "Alex",
        "--role", "student", "--tutor", "sam@example.com",
    ) == 0  # fmt: skip
    assert run("users", "lock", "alex@example.com", "--reason", "Spam") == 0
    capsys.readouterr()

    assert run("users", "list") == 0
    listing = capsys.readouterr().out.splitlines()
    assert listing[0].startswith("alex@example.com\tAlex\tstudent\taccount_locked")
    assert listing[1].startswith("sam@example.com\tSam\ttutor\tactive")

    assert run("users", "add", "--email", "bad", "--name", "X", "--role", "tutor") == 1
    assert "Invalid email" in capsys.readouterr().err
