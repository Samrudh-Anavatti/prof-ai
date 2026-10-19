import json
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from prof_ai.auth import PRINCIPAL_HEADER
from prof_ai.chat.limits import TurnLimiter
from prof_ai.chat.models import Conversation, PromptMessage, Usage
from prof_ai.chat.service import ChatLimits, ChatService
from prof_ai.config import Settings
from prof_ai.main import create_app
from prof_ai.profiles.store import ProfileStore
from prof_ai.users.models import Role
from tests.auth.conftest import InMemoryUserRepository, make_user, principal_header

FIXED_NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)
PRODUCTION = Settings(app_env="production", on_app_service=True, platform_auth_enabled=True)


class InMemoryBlobBackend:
    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], bytes] = {}

    def upload(self, container: str, name: str, data: bytes, content_type: str) -> None:
        self.blobs[(container, name)] = data

    def download(self, container: str, name: str) -> bytes:
        return self.blobs[(container, name)]

    def exists(self, container: str, name: str) -> bool:
        return (container, name) in self.blobs

    def list_names(self, container: str, prefix: str) -> Iterable[str]:
        return [n for (c, n) in self.blobs if c == container and n.startswith(prefix)]

    def delete(self, container: str, name: str) -> None:
        del self.blobs[(container, name)]


class InMemoryChatStore:
    def __init__(self) -> None:
        self.conversations: dict[tuple[str, str], dict] = {}
        self.usage: dict[tuple[str, date], int] = {}
        self.tokens: dict[tuple[str, date], int] = {}
        self.fail_saves = False

    def list_conversations(self, user_id: str) -> list[Conversation]:
        chats = [
            Conversation.model_validate(c)
            for (u, _), c in self.conversations.items()
            if u == user_id
        ]
        return sorted(chats, key=lambda c: c.updated_at, reverse=True)

    def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        item = self.conversations.get((user_id, conversation_id))
        return Conversation.model_validate(item) if item else None

    def save_conversation(self, conversation: Conversation) -> None:
        if self.fail_saves:
            raise ConnectionError("store down")
        key = (conversation.user_id, conversation.id)
        self.conversations[key] = conversation.model_dump(mode="json")

    def cost_used(self, user_id: str, day: date) -> int:
        return self.usage.get((user_id, day), 0)

    def cost_used_by_everyone(self, day: date) -> int:
        return sum(cost for (_, d), cost in self.usage.items() if d == day)

    def add_usage(self, user_id: str, day: date, tokens: int, cost_micro_usd: int) -> None:
        self.usage[(user_id, day)] = self.usage.get((user_id, day), 0) + cost_micro_usd
        self.tokens[(user_id, day)] = self.tokens.get((user_id, day), 0) + tokens

    def delete_user_data(self, user_id: str) -> None:
        self.conversations = {k: v for k, v in self.conversations.items() if k[0] != user_id}
        self.usage = {k: v for k, v in self.usage.items() if k[0] != user_id}
        self.tokens = {k: v for k, v in self.tokens.items() if k[0] != user_id}


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[list[PromptMessage]] = []
        self.output_caps: list[int] = []
        self.reply = ["Good ", "question! ", "What do you know already?"]
        self.usage = Usage(input_tokens=120, output_tokens=30)
        self.error: Exception | None = None

    @property
    def system_prompts(self) -> list[str]:
        return [call[0].content for call in self.calls]

    def stream(
        self, messages: Sequence[PromptMessage], max_output_tokens: int
    ) -> Iterator[str | Usage]:
        self.calls.append(list(messages))
        self.output_caps.append(max_output_tokens)
        yield from self.reply
        if self.error:
            raise self.error
        yield self.usage


class Harness:
    def __init__(self, limits: ChatLimits | None = None, model: FakeModel | None = None) -> None:
        self.users = InMemoryUserRepository()
        self.blobs = InMemoryBlobBackend()
        self.profiles = ProfileStore(self.blobs)
        self.store = InMemoryChatStore()
        self.model = model or FakeModel()
        self.limits = limits or ChatLimits()
        self.users.save(make_user("sam", role=Role.TUTOR, email="sam@example.com"))
        self.users.save(make_user("punjy", role=Role.TUTOR, email="punjy@example.com"))
        self.users.save(make_user("alex", tutor_id="sam", email="alex@example.com"))
        self.users.save(make_user("bea", tutor_id="punjy", email="bea@example.com"))
        self.service = ChatService(
            self.model,
            self.store,
            self.profiles,
            self.limits,
            limiter=TurnLimiter(per_minute=1000),
            clock=lambda: FIXED_NOW,
        )
        self.client = TestClient(
            create_app(PRODUCTION, user_repository=self.users, chat_service=self.service)
        )

    def as_user(self, user_id: str) -> dict[str, str]:
        return {PRINCIPAL_HEADER: principal_header(user_id)}

    def start(self, user_id: str) -> str:
        response = self.client.post("/api/chat/conversations", headers=self.as_user(user_id))
        assert response.status_code == 201
        return response.json()["id"]

    def send(self, user_id: str, conversation_id: str, content: str):
        return self.client.post(
            f"/api/chat/conversations/{conversation_id}/messages",
            json={"content": content},
            headers=self.as_user(user_id),
        )


def parse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def harness() -> Harness:
    return Harness()
