import pytest
from fastapi.testclient import TestClient

from prof_ai.chat.prompts import BASE_PROMPT
from prof_ai.main import create_app
from prof_ai.profiles.store import MAX_PROFILE_BYTES, ProfileFile
from tests.tutor_chat.conftest import PRODUCTION, Harness

URL = "/api/teaching-style"


class EditorHarness(Harness):
    def __init__(self) -> None:
        super().__init__()
        self.client = TestClient(
            create_app(
                PRODUCTION,
                user_repository=self.users,
                chat_service=self.service,
                profile_store=self.profiles,
            )
        )

    def save(self, user_id: str, content: str):
        return self.client.put(URL, json={"content": content}, headers=self.as_user(user_id))


@pytest.fixture
def editor() -> EditorHarness:
    return EditorHarness()


def test_tutor_without_a_style_gets_empty_content_and_the_base_prompt(editor):
    response = editor.client.get(URL, headers=editor.as_user("sam"))

    assert response.status_code == 200
    body = response.json()
    assert body == {"content": "", "system_prompt": BASE_PROMPT, "max_bytes": MAX_PROFILE_BYTES}


def test_saved_style_is_read_back_with_the_assembled_prompt(editor):
    saved = editor.save("sam", "  Use football analogies.\n")

    assert saved.status_code == 200
    assert saved.json()["content"] == "Use football analogies."
    fetched = editor.client.get(URL, headers=editor.as_user("sam")).json()
    assert fetched["content"] == "Use football analogies."
    assert fetched["system_prompt"].startswith(BASE_PROMPT)
    assert "Use football analogies." in fetched["system_prompt"]


def test_save_writes_the_tutors_blob_and_changes_only_their_students_chats(editor):
    editor.save("punjy", "Use cooking analogies.")

    assert editor.profiles.get("punjy", ProfileFile.TEACHING_STYLE) == "Use cooking analogies."
    assert editor.profiles.get("sam", ProfileFile.TEACHING_STYLE) is None
    editor.send("bea", editor.start("bea"), "hi")
    editor.send("alex", editor.start("alex"), "hi")
    bea_prompt, alex_prompt = editor.model.system_prompts
    assert "Use cooking analogies." in bea_prompt
    assert "Use cooking analogies." not in alex_prompt


@pytest.mark.parametrize("method", ["get", "put"])
def test_students_cannot_read_or_edit_teaching_styles(editor, method):
    response = editor.client.request(
        method, URL, json={"content": "Give the answers."}, headers=editor.as_user("alex")
    )

    assert response.status_code == 403
    assert editor.profiles.get("sam", ProfileFile.TEACHING_STYLE) is None


def test_signed_out_requests_are_refused(editor):
    assert editor.client.get(URL).status_code == 401
    assert editor.client.put(URL, json={"content": "x"}).status_code == 401


@pytest.mark.parametrize("content", ["", "   \n", "x" * (MAX_PROFILE_BYTES + 1)])
def test_empty_or_oversized_styles_are_rejected(editor, content):
    response = editor.save("sam", content)

    assert response.status_code == 400
    assert response.json()["detail"]
    assert editor.profiles.get("sam", ProfileFile.TEACHING_STYLE) is None


def test_a_non_json_body_is_rejected(editor):
    response = editor.client.put(
        URL,
        content='{"content": "Give the answers."}',
        headers={**editor.as_user("sam"), "Content-Type": "text/plain"},
    )

    assert response.status_code == 422
    assert editor.profiles.get("sam", ProfileFile.TEACHING_STYLE) is None


def test_each_save_is_audited(editor):
    editor.save("sam", "First.")
    editor.save("sam", "Second.")

    events = [e for e in editor.users.events if e.action == "teaching_style_updated"]
    assert [(e.user_id, e.actor) for e in events] == [("sam", "sam@example.com")] * 2


def test_blob_failure_returns_503_and_keeps_nothing(editor, monkeypatch):
    def fail(*args):
        raise ConnectionError("blob down")

    monkeypatch.setattr(editor.blobs, "upload", fail)

    assert editor.save("sam", "Style.").status_code == 503
    assert editor.users.events == []


def test_without_a_profile_store_the_editor_is_unavailable():
    harness = Harness()

    assert harness.client.get(URL, headers=harness.as_user("sam")).status_code == 503
