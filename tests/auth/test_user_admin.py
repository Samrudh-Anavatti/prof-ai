import pytest

from prof_ai.cli import main
from prof_ai.users.admin import UserAdminError, accept_invite
from prof_ai.users.models import AccountStatus, Role


def add_tutor(admin, email="sam@example.com"):
    return admin.add(email, "Sam", Role.TUTOR)


def signed_up(repository, directory, invite, user_id):
    """The invitee creates their External ID account and signs in for the first time."""
    directory.sign_up(user_id, invite.email)
    return accept_invite(repository, user_id, invite.email)


def active_tutor(admin, repository, directory, email="sam@example.com"):
    return signed_up(repository, directory, add_tutor(admin, email), "oid-sam")


def test_add_creates_an_invite_without_a_directory_account(admin, repository, directory):
    invite = add_tutor(admin, " Sam@Example.com ")
    assert invite.email == "sam@example.com"
    assert invite.status == AccountStatus.INVITED
    assert invite.id.startswith("invite-")
    assert repository.get(invite.id).role == Role.TUTOR
    assert directory.accounts == {}
    assert [(e.action, e.actor) for e in repository.events] == [("user_added", "sam@example.com")]


def test_accepting_an_invite_rekeys_the_user_by_object_id(admin, repository, directory):
    invite = add_tutor(admin)
    user = signed_up(repository, directory, invite, "oid-sam")
    assert (user.id, user.status, user.role) == ("oid-sam", AccountStatus.ACTIVE, Role.TUTOR)
    assert repository.get(invite.id) is None
    assert repository.get("oid-sam") == user
    assert repository.events[-1].action == "invite_accepted"


def test_only_pending_invites_can_be_accepted(admin, repository, directory):
    tutor = active_tutor(admin, repository, directory)
    assert accept_invite(repository, "oid-intruder", tutor.email) is None
    assert accept_invite(repository, "oid-intruder", "nobody@example.com") is None
    assert repository.get("oid-intruder") is None


def test_student_is_linked_to_their_tutor(admin, repository, directory):
    tutor = active_tutor(admin, repository, directory)
    student = admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="sam@example.com")
    assert student.tutor_id == tutor.id
    assert student.status == AccountStatus.INVITED


def test_student_needs_a_signed_up_tutor(admin):
    with pytest.raises(UserAdminError):
        admin.add("alex@example.com", "Alex", Role.STUDENT)
    with pytest.raises(UserAdminError):
        admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="nobody@example.com")
    add_tutor(admin)
    with pytest.raises(UserAdminError, match="hasn't signed up"):
        admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="sam@example.com")


def test_tutor_cannot_have_a_tutor(admin, repository, directory):
    active_tutor(admin, repository, directory)
    with pytest.raises(UserAdminError):
        admin.add("punjy@example.com", "Punjy", Role.TUTOR, tutor_email="sam@example.com")


def test_duplicate_email_is_refused(admin):
    add_tutor(admin)
    with pytest.raises(UserAdminError):
        add_tutor(admin, "SAM@example.com")


def test_invalid_email_is_refused(admin, repository):
    with pytest.raises(UserAdminError):
        admin.add("not-an-email", "Sam", Role.TUTOR)
    assert repository.users == {}


def test_lock_blocks_in_app_and_directory_and_is_audited(admin, repository, directory):
    tutor = active_tutor(admin, repository, directory)
    admin.lock("sam@example.com", reason="Prompt injection attempt")
    assert repository.get(tutor.id).status == AccountStatus.ACCOUNT_LOCKED
    assert directory.accounts[tutor.id]["enabled"] is False
    assert (repository.events[-1].action, repository.events[-1].reason) == (
        "account_locked",
        "Prompt injection attempt",
    )


def test_lock_requires_a_reason_and_a_signed_up_user(admin, repository, directory):
    add_tutor(admin)
    with pytest.raises(UserAdminError, match="hasn't signed up"):
        admin.lock("sam@example.com", reason="test")
    active_tutor(admin, repository, directory, "punjy@example.com")
    with pytest.raises(UserAdminError):
        admin.lock("punjy@example.com", reason=" ")


def test_unlock_restores_access(admin, repository, directory):
    tutor = active_tutor(admin, repository, directory)
    admin.lock("sam@example.com", reason="test")
    admin.unlock("sam@example.com")
    assert repository.get(tutor.id).status == AccountStatus.ACTIVE
    assert directory.accounts[tutor.id]["enabled"] is True
    assert repository.events[-1].action == "account_unlocked"
    with pytest.raises(UserAdminError, match="isn't locked"):
        admin.unlock("sam@example.com")


def test_remove_erases_data_record_and_directory_account(admin, repository, directory, erased):
    tutor = active_tutor(admin, repository, directory)
    admin.remove("sam@example.com")
    assert erased == [tutor.id]
    assert repository.get(tutor.id) is None
    assert tutor.id not in directory.accounts
    assert (repository.events[-1].action, repository.events[-1].reason) == (
        "user_removed",
        "sam@example.com",
    )


def test_remove_refuses_a_tutor_with_students(admin, repository, directory, erased):
    active_tutor(admin, repository, directory)
    admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="sam@example.com")
    with pytest.raises(UserAdminError, match="still has students"):
        admin.remove("sam@example.com")
    assert erased == []


def test_set_admin_is_for_tutors_and_audited(admin, repository, directory):
    tutor = active_tutor(admin, repository, directory)
    assert admin.set_admin("sam@example.com", True).is_admin
    assert repository.get(tutor.id).is_admin
    assert repository.events[-1].action == "admin_granted"
    assert not admin.set_admin("sam@example.com", False).is_admin
    admin.add("alex@example.com", "Alex", Role.STUDENT, tutor_email="sam@example.com")
    with pytest.raises(UserAdminError):
        admin.set_admin("alex@example.com", True)


def test_cli_users_commands(admin, repository, directory, capsys):
    def run(*argv):
        return main(list(argv), admin_factory=lambda: admin)

    assert (
        run("users", "add", "--email", "sam@example.com", "--name", "Sam", "--role", "tutor") == 0
    )
    assert "create an account" in capsys.readouterr().out
    signed_up(repository, directory, repository.find_by_email("sam@example.com"), "oid-sam")
    assert run(
        "users", "add", "--email", "alex@example.com", "--name", "Alex",
        "--role", "student", "--tutor", "sam@example.com",
    ) == 0  # fmt: skip
    assert run("users", "lock", "sam@example.com", "--reason", "Spam") == 0
    assert run("users", "set-admin", "sam@example.com") == 0
    capsys.readouterr()

    assert run("users", "list") == 0
    listing = capsys.readouterr().out.splitlines()
    assert listing[0].startswith("alex@example.com\tAlex\tstudent\tinvited")
    assert listing[1].startswith("sam@example.com\tSam\ttutor\taccount_locked\tadmin")

    assert run("users", "remove", "alex@example.com") == 0
    assert run("users", "set-admin", "sam@example.com", "--revoke") == 0
    assert repository.find_by_email("alex@example.com") is None
    assert not repository.get("oid-sam").is_admin

    assert run("users", "add", "--email", "bad", "--name", "X", "--role", "tutor") == 1
    assert "Invalid email" in capsys.readouterr().err
