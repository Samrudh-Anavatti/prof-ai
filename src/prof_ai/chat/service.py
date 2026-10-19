import logging
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from prof_ai.chat.context import (
    AssembledContext,
    ContextInput,
    ContextOverflowError,
    assemble,
    check_budget,
)
from prof_ai.chat.limits import TurnLimiter
from prof_ai.chat.memory import (
    SUMMARY_OUTPUT_TOKENS,
    clip_summary,
    messages_to_summarise,
    summary_request,
)
from prof_ai.chat.model import ChatModel, ContentFilteredError
from prof_ai.chat.model_profiles import LUNA, ModelProfile
from prof_ai.chat.models import (
    ChatMessage,
    Conversation,
    Flag,
    PromptMessage,
    TurnContext,
    Usage,
)
from prof_ai.chat.prompts import load_profile_layers
from prof_ai.chat.store import ChatStore
from prof_ai.profiles.store import ProfileStore
from prof_ai.users.models import Role, User

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 2000
MAX_MESSAGES_PER_CONVERSATION = 200
TITLE_CHARS = 60
MICRO_USD = 1_000_000
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
    daily_user_usd: float = 0.50
    daily_global_usd: float = 1.50


@dataclass(frozen=True)
class ChatEvent:
    kind: Literal["delta", "done", "error"]
    data: dict


@dataclass(frozen=True)
class Turn:
    user: User
    conversation: Conversation
    message: ChatMessage
    context: AssembledContext


class ChatService:
    """The only path to the model: every call is capped, budgeted and recorded here."""

    def __init__(
        self,
        model: ChatModel,
        store: ChatStore,
        profiles: ProfileStore,
        limits: ChatLimits,
        limiter: TurnLimiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        model_profile: ModelProfile = LUNA,
    ):
        check_budget(model_profile)
        self._model = model
        self._store = store
        self._profiles = profiles
        self._limits = limits
        self._limiter = limiter or TurnLimiter()
        self._clock = clock
        self._profile = model_profile

    def list_conversations(self, user: User) -> list[Conversation]:
        return self._store.list_conversations(user.id)

    def erase_user_data(self, user_id: str) -> None:
        self._store.delete_user_data(user_id)

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
        context = self._assemble(user, conversation, content)
        wait_reason = self._limiter.try_acquire(user.id)
        if wait_reason:
            raise ChatRefusedError(429, wait_reason)
        message = ChatMessage(role="user", content=content, at=self._clock())
        return Turn(user, conversation, message, context)

    def run_turn(self, turn: Turn) -> Iterator[ChatEvent]:
        try:
            yield from self._run_turn(turn)
        finally:
            self._limiter.release(turn.user.id)

    def _assemble(self, user: User, conversation: Conversation, content: str) -> AssembledContext:
        try:
            layers = load_profile_layers(user, self._profiles)
            return assemble(
                ContextInput(
                    message=content,
                    teaching_style=layers.teaching_style,
                    profile=layers.profile,
                    summary=conversation.summary,
                    history=conversation.messages,
                )
            )
        except ContextOverflowError:
            logger.exception("Context over its caps for conversation %s", conversation.id)
            raise ChatRefusedError(503, UNAVAILABLE) from None
        except Exception as error:
            logger.exception("Assembling context failed for conversation %s", conversation.id)
            raise ChatRefusedError(503, UNAVAILABLE) from error

    def _check_budgets(self, user: User) -> None:
        today = self._clock().date()
        try:
            user_spend = 0 if user.role == Role.TUTOR else self._store.cost_used(user.id, today)
            everyone_spend = self._store.cost_used_by_everyone(today)
        except Exception as error:
            raise ChatRefusedError(503, UNAVAILABLE) from error
        if user_spend >= self._limits.daily_user_usd * MICRO_USD:
            raise ChatRefusedError(
                429, "You've used today's chat allowance. It resets at midnight UTC."
            )
        if everyone_spend >= self._limits.daily_global_usd * MICRO_USD:
            raise ChatRefusedError(503, "Chat is paused for the rest of today.")

    def _run_turn(self, turn: Turn) -> Iterator[ChatEvent]:
        conversation = turn.conversation
        reply: list[str] = []
        usage: Usage | None = None
        try:
            for item in self._model.stream(turn.context.messages, self._profile.max_output_tokens):
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
        ledger = TurnContext(
            layers=turn.context.layers, estimated_input=turn.context.estimated_input
        )
        if usage:
            ledger = ledger.model_copy(
                update={
                    "input_tokens": usage.input_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_micro_usd": self._profile.cost_micro_usd(usage),
                }
            )
            logger.info(
                "Context for %s: estimated %d tokens, reported %d (%d cached)",
                conversation.id,
                ledger.estimated_input,
                usage.input_tokens,
                usage.cached_input_tokens,
            )
        answer = ChatMessage(role="assistant", content="".join(reply), at=now, context=ledger)
        conversation.messages.extend([turn.message, answer])
        conversation.title = conversation.title or turn.message.content[:TITLE_CHARS]
        conversation.updated_at = now
        try:
            self._save_with_usage(turn.user, conversation, usage)
        except Exception:
            logger.exception("Saving chat turn failed for conversation %s", conversation.id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return
        self._summarise_if_due(turn.user, conversation)
        yield ChatEvent("done", {"title": conversation.title})

    def _save_with_usage(self, user: User, conversation: Conversation, usage: Usage | None) -> None:
        if usage:
            conversation.input_tokens += usage.input_tokens
            conversation.output_tokens += usage.output_tokens
        self._store.save_conversation(conversation)
        if usage:
            day = self._clock().date()
            self._store.add_usage(user.id, day, usage.total, self._profile.cost_micro_usd(usage))

    def _summarise_if_due(self, user: User, conversation: Conversation) -> None:
        """Fold old messages into the summary. A failure is retried on the next turn."""
        batch = messages_to_summarise(conversation)
        if not batch:
            return
        try:
            if self._store.cost_used_by_everyone(self._clock().date()) >= (
                self._limits.daily_global_usd * MICRO_USD
            ):
                return
            text, usage = self._complete(summary_request(conversation.summary, batch))
            summary = clip_summary(text)
            if summary:
                conversation.summary = summary
                conversation.summarised_count += len(batch)
            else:
                logger.warning("Empty summary for conversation %s", conversation.id)
            self._save_with_usage(user, conversation, usage)
        except Exception:
            logger.exception("Summarising failed for conversation %s", conversation.id)

    def _complete(self, messages: Sequence[PromptMessage]) -> tuple[str, Usage | None]:
        parts: list[str] = []
        usage: Usage | None = None
        for item in self._model.stream(messages, SUMMARY_OUTPUT_TOKENS):
            if isinstance(item, Usage):
                usage = item
            else:
                parts.append(item)
        return "".join(parts), usage

    def _record_filter_hit(self, turn: Turn) -> None:
        conversation = turn.conversation
        conversation.flags.append(
            Flag(kind="content_filter", message=turn.message.content, at=turn.message.at)
        )
        try:
            self._store.save_conversation(conversation)
        except Exception:
            logger.exception("Recording a content filter flag failed for %s", conversation.id)
