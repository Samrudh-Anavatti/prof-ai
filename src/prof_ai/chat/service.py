import logging
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from prof_ai.chat.limits import TurnLimiter
from prof_ai.chat.model import ChatModel, ContentFilteredError
from prof_ai.chat.models import ChatMessage, Conversation, Flag, Usage
from prof_ai.chat.prompts import build_system_prompt
from prof_ai.chat.store import ChatStore
from prof_ai.profiles.store import ProfileStore
from prof_ai.users.models import User

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 2000
HISTORY_MESSAGES = 20
MAX_MESSAGES_PER_CONVERSATION = 200
TITLE_CHARS = 60
UNAVAILABLE = "Prof AI is unavailable right now. Try again later."
FILTERED = "Sorry, I can't help with that. Try asking another way, or talk to your tutor."


class ChatRefusedError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ConversationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ChatLimits:
    enabled: bool = True
    daily_user_tokens: int = 50_000
    daily_global_tokens: int = 500_000


@dataclass(frozen=True)
class ChatEvent:
    kind: Literal["delta", "done", "error"]
    data: dict


@dataclass(frozen=True)
class Turn:
    user: User
    conversation: Conversation
    message: ChatMessage


class ChatService:
    def __init__(
        self,
        model: ChatModel,
        store: ChatStore,
        profiles: ProfileStore,
        limits: ChatLimits,
        limiter: TurnLimiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._model = model
        self._store = store
        self._profiles = profiles
        self._limits = limits
        self._limiter = limiter or TurnLimiter()
        self._clock = clock

    def list_conversations(self, user: User) -> list[Conversation]:
        return self._store.list_conversations(user.id)

    def start_conversation(self, user: User) -> Conversation:
        now = self._clock()
        conversation = Conversation(
            id=uuid.uuid4().hex, user_id=user.id, created_at=now, updated_at=now
        )
        self._store.save_conversation(conversation)
        return conversation

    def get_conversation(self, user: User, conversation_id: str) -> Conversation:
        conversation = self._store.get_conversation(user.id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation

    def begin_turn(self, user: User, conversation_id: str, content: str) -> Turn:
        """Run every check that can refuse a message, before any model call."""
        content = content.strip()
        if not self._limits.enabled:
            raise ChatRefusedError(503, "Chat is switched off at the moment.")
        if not content:
            raise ChatRefusedError(400, "Type a message first.")
        if len(content) > MAX_INPUT_CHARS:
            raise ChatRefusedError(
                400, f"That message is too long. Keep it under {MAX_INPUT_CHARS} characters."
            )
        conversation = self.get_conversation(user, conversation_id)
        if len(conversation.messages) >= MAX_MESSAGES_PER_CONVERSATION:
            raise ChatRefusedError(409, "This chat is full. Start a new one.")
        self._check_budgets(user)
        wait_reason = self._limiter.try_acquire(user.id)
        if wait_reason:
            raise ChatRefusedError(429, wait_reason)
        return Turn(user, conversation, ChatMessage(role="user", content=content, at=self._clock()))

    def run_turn(self, turn: Turn) -> Iterator[ChatEvent]:
        try:
            yield from self._run_turn(turn)
        finally:
            self._limiter.release(turn.user.id)

    def _check_budgets(self, user: User) -> None:
        today = self._clock().date()
        try:
            user_tokens = self._store.tokens_used(user.id, today)
            everyone_tokens = self._store.tokens_used_by_everyone(today)
        except Exception as error:
            raise ChatRefusedError(503, UNAVAILABLE) from error
        if user_tokens >= self._limits.daily_user_tokens:
            raise ChatRefusedError(
                429, "You've used today's chat allowance. It resets at midnight UTC."
            )
        if everyone_tokens >= self._limits.daily_global_tokens:
            raise ChatRefusedError(503, "Chat is paused for the rest of today.")

    def _run_turn(self, turn: Turn) -> Iterator[ChatEvent]:
        conversation = turn.conversation
        history = [*conversation.messages, turn.message][-HISTORY_MESSAGES:]
        reply: list[str] = []
        usage: Usage | None = None
        try:
            system_prompt = build_system_prompt(turn.user, self._profiles)
            for item in self._model.stream(system_prompt, history):
                if isinstance(item, Usage):
                    usage = item
                else:
                    reply.append(item)
                    yield ChatEvent("delta", {"text": item})
        except ContentFilteredError:
            self._record_filter_hit(turn)
            yield ChatEvent("error", {"message": FILTERED})
            return
        except Exception:
            logger.exception("Chat turn failed for conversation %s", conversation.id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return

        now = self._clock()
        answer = ChatMessage(role="assistant", content="".join(reply), at=now)
        conversation.messages.extend([turn.message, answer])
        conversation.title = conversation.title or turn.message.content[:TITLE_CHARS]
        conversation.updated_at = now
        if usage:
            conversation.input_tokens += usage.input_tokens
            conversation.output_tokens += usage.output_tokens
        try:
            self._store.save_conversation(conversation)
            if usage:
                self._store.add_tokens(turn.user.id, now.date(), usage.total)
        except Exception:
            logger.exception("Saving chat turn failed for conversation %s", conversation.id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return
        yield ChatEvent("done", {"title": conversation.title})

    def _record_filter_hit(self, turn: Turn) -> None:
        conversation = turn.conversation
        conversation.flags.append(
            Flag(kind="content_filter", message=turn.message.content, at=turn.message.at)
        )
        try:
            self._store.save_conversation(conversation)
        except Exception:
            logger.exception("Recording a content filter flag failed for %s", conversation.id)
