from datetime import timedelta

import pytest

from tests.lessons.conftest import RATIOS, LessonHarness
from tests.tutor_chat.conftest import FIXED_NOW, parse_events


class Clock:
    """Moves on a second each time it's read, so every write gets a new updated_at."""

    def __init__(self) -> None:
        self.now = FIXED_NOW

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class SharedHarness(LessonHarness):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.users.save(self.users.get("sam").model_copy(update={"display_name": "Sam"}))
        self.users.save(self.users.get("punji").model_copy(update={"display_name": "Punji"}))
        self.chat_id = self.create("sam", "alex", RATIOS).json()["id"]

    def student_says(self, content: str, to_tutor: bool = False):
        return self.client.post(
            f"/api/chat/conversations/{self.chat_id}/messages",
            json={"content": content, "to_tutor": to_tutor},
            headers=self.as_user("alex"),
        )

    def tutor_says(self, content: str, tutor: str = "sam"):
        return self.client.post(
            f"/api/students/alex/chats/{self.chat_id}/messages",
            json={"content": content},
            headers=self.as_user(tutor),
        )

    def detail(self, as_user: str = "alex") -> dict:
        path = (
            f"/api/chat/conversations/{self.chat_id}"
            if as_user == "alex"
            else f"/api/students/alex/chats/{self.chat_id}"
        )
        return self.client.get(path, headers=self.as_user(as_user)).json()

    def done(self, response) -> dict:
        kind, data = parse_events(response.text)[-1]
        assert kind == "done", data
        return data


@pytest.fixture
def h() -> SharedHarness:
    return SharedHarness(clock=Clock())
