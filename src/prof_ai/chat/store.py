from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from prof_ai.chat.models import Conversation


class ChatStore(Protocol):
    def list_conversations(self, user_id: str) -> list[Conversation]: ...

    def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None: ...

    def save_conversation(self, conversation: Conversation) -> None: ...

    def delete_conversation(self, user_id: str, conversation_id: str) -> None: ...

    def update_conversation(
        self, user_id: str, conversation_id: str, change: Callable[[Conversation], None]
    ) -> Conversation:
        """Apply change to the latest copy and save it, without losing a concurrent write."""
        ...

    def conversation_version(self, user_id: str, conversation_id: str) -> datetime | None:
        """When the conversation last changed; cheap enough to poll."""
        ...

    def cost_used(self, user_id: str, day: date) -> int:
        """Micro-dollars spent by the user on that UTC day."""
        ...

    def cost_used_by_everyone(self, day: date) -> int: ...

    def add_usage(self, user_id: str, day: date, tokens: int, cost_micro_usd: int) -> None: ...

    def delete_user_data(self, user_id: str) -> None: ...
