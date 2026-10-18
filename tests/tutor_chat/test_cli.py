from prof_ai.cli import TutorTools, main
from prof_ai.profiles.store import ProfileFile


def run(harness, capsys, *argv):
    tools = TutorTools(harness.users, harness.profiles, harness.store)
    code = main([str(arg) for arg in argv], tools_factory=lambda: tools)
    out, err = capsys.readouterr()
    return code, out, err


def test_profiles_set_and_show(harness, capsys, tmp_path):
    profile = tmp_path / "alex.md"
    profile.write_text("Alex, Year 9, finds algebra hard.")
    code, out, _ = run(harness, capsys, "profiles", "set", "ALEX@example.com", "--profile", profile)
    assert code == 0
    assert harness.profiles.get("alex", ProfileFile.PROFILE) == "Alex, Year 9, finds algebra hard."

    code, out, _ = run(harness, capsys, "profiles", "show", "alex@example.com")
    assert code == 0
    assert "--- system prompt ---" in out
    assert out.count("Alex, Year 9, finds algebra hard.") == 2


def test_teaching_style_is_for_tutors_only(harness, capsys, tmp_path):
    style = tmp_path / "style.md"
    style.write_text("Worked examples first.")
    code, _, err = run(
        harness, capsys, "profiles", "set", "alex@example.com", "--teaching-style", style
    )
    assert code == 1
    assert "Only tutors" in err
    code, _, _ = run(
        harness, capsys, "profiles", "set", "sam@example.com", "--teaching-style", style
    )
    assert code == 0
    assert harness.profiles.get("sam", ProfileFile.TEACHING_STYLE) == "Worked examples first."


def test_unknown_email_is_an_error(harness, capsys):
    code, _, err = run(harness, capsys, "profiles", "show", "nobody@example.com")
    assert code == 1
    assert "No account" in err


def test_chats_list_and_show_transcript(harness, capsys):
    conversation_id = harness.start("alex")
    harness.send("alex", conversation_id, "What is a prime number?")
    code, out, _ = run(harness, capsys, "chats", "list", "alex@example.com")
    assert code == 0
    assert conversation_id in out
    assert "150 tokens" in out
    assert "What is a prime number?" in out

    code, out, _ = run(harness, capsys, "chats", "show", "alex@example.com", conversation_id)
    assert code == 0
    assert "user:\nWhat is a prime number?" in out
    assert "assistant:\nGood question! What do you know already?" in out


def test_chats_show_refuses_another_users_conversation(harness, capsys):
    conversation_id = harness.start("alex")
    code, _, err = run(harness, capsys, "chats", "show", "bea@example.com", conversation_id)
    assert code == 1
    assert "No chat" in err
