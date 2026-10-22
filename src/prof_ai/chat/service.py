import logging
import re
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from prof_ai.chat.checking import (
    CHECK_OUTPUT_TOKENS,
    FEEDBACK,
    KEEP_GOING,
    MAX_ANSWER_CHARS,
    CheckError,
    find_question,
    leaks_key,
    mark_request,
    matches_key,
    missing_working,
    parse_mark,
    parse_working_check,
    question_reference,
    shown_first_step,
    tidy_working,
    working_check_request,
    working_message,
)
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
from prof_ai.chat.model import ChatModel, ContentFilteredError, ModelRateLimitedError
from prof_ai.chat.model_profiles import LUNA, ModelProfile
from prof_ai.chat.models import (
    Attempt,
    Author,
    ChatMessage,
    Conversation,
    Flag,
    Lesson,
    PromptMessage,
    Question,
    SupportLevel,
    TurnContext,
    Usage,
    Verdict,
)
from prof_ai.chat.prompts import SUPPORT_PROMPTS, load_profile_layers
from prof_ai.chat.store import ChatStore
from prof_ai.lessons.answers import (
    SOLVE_OUTPUT_TOKENS,
    AnswersError,
    QuestionToSolve,
    SolvedAnswer,
    parse_answers,
    solve_request,
)
from prof_ai.lessons.describe import (
    DRAFT_OUTPUT_TOKENS,
    DraftError,
    LessonDraft,
    draft_request,
    parse_draft,
)
from prof_ai.lessons.first_steps import (
    FIRST_STEPS_OUTPUT_TOKENS,
    FirstStep,
    FirstStepsError,
    QuestionToStart,
    first_steps_request,
    parse_first_steps,
)
from prof_ai.lessons.rules import InvalidLessonError, render_lesson, validate_lesson
from prof_ai.lessons.worksheet import (
    EXTRACT_OUTPUT_TOKENS,
    Worksheet,
    WorksheetError,
    extraction_request,
    parse_worksheet,
)
from prof_ai.profiles.store import ProfileStore
from prof_ai.users.models import Role, User

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 2000
MAX_MESSAGES_PER_CONVERSATION = 200
MAX_CHATS_PER_STUDENT = 5
TITLE_CHARS = 60
MICRO_USD = 1_000_000
UNAVAILABLE = "Prof AI is unavailable right now. Try again later."
BUSY = "Prof AI is busy right now. Try again in a minute."
# Shown for every filter hit, including self-harm disclosures, so it must point to help (R11).
FILTERED = (
    "I can't reply to that message, and your tutor will be able to see it. "
    "If you're upset or worried about your safety, please talk to your tutor, a parent or "
    "another adult you trust straight away. You can also call Childline free on 0800 1111 "
    "or visit childline.org.uk."
)


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


# A whole word, so addresses like sam@ai.example don't count.
AI_MENTION = re.compile(r"(?<![\w@.])@ai\b", re.IGNORECASE)


def author_of(user: User) -> Author:
    return "tutor" if user.role == Role.TUTOR else "student"


def asks_ai(
    conversation: Conversation,
    content: str,
    author: Author = "student",
    to_tutor: bool = False,
    owner_author: Author = "student",
) -> bool:
    """In a lesson chat, its owner gets Prof AI unless they write to their tutor only, and
    anyone else (the student's tutor) asks with @AI. Other chats answer every message."""
    if conversation.lesson is None or AI_MENTION.search(content):
        return True
    return author == owner_author and not to_tutor


@dataclass(frozen=True)
class AvailableModel:
    profile: ModelProfile
    model: ChatModel
    # None for providers without a per-minute token quota.
    tokens_per_minute: int | None = None


@dataclass(frozen=True)
class CheckResult:
    verdict: Verdict
    feedback: str
    conversation: Conversation

    @property
    def correct(self) -> bool:
        return self.verdict == "correct"


@dataclass(frozen=True)
class WorkingFeedback:
    feedback: str
    conversation: Conversation


@dataclass(frozen=True)
class Turn:
    sender: User
    owner: User
    conversation: Conversation
    message: ChatMessage
    # None when nobody asked Prof AI: the message is just saved.
    context: AssembledContext | None
    engine: AvailableModel | None = None


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
        tokens_per_minute: int | None = 50_000,
        extra_models: Sequence[AvailableModel] = (),
    ):
        self._default = AvailableModel(model_profile, model, tokens_per_minute)
        self._models = {m.profile.deployment: m for m in (self._default, *extra_models)}
        for available in self._models.values():
            check_budget(available.profile, available.tokens_per_minute)
        self._store = store
        self._profiles = profiles
        self._limits = limits
        self._limiter = limiter or TurnLimiter()
        self._clock = clock

    @property
    def default_model(self) -> ModelProfile:
        return self._default.profile

    def models(self) -> list[ModelProfile]:
        return [available.profile for available in self._models.values()]

    def check_model(self, owner: User, model_id: str) -> None:
        """Refuse a model that isn't registered, or isn't approved for a student's chat."""
        available = self._models.get(model_id)
        if available is None:
            raise ChatRefusedError(400, "That model isn't available.")
        if owner.role == Role.STUDENT and not available.profile.approved_for_student_conversations:
            raise ChatRefusedError(
                400, f"{available.profile.label} isn't approved for student conversations."
            )

    def list_conversations(self, user: User) -> list[Conversation]:
        return self._store.list_conversations(user.id)

    def erase_user_data(self, user_id: str) -> None:
        self._store.delete_user_data(user_id)

    def create_chat(
        self,
        actor: User,
        student: User,
        lesson: Lesson | None = None,
        licence_confirmed: bool = False,
        model: str | None = None,
    ) -> Conversation:
        """A chat for one student. Callers check that the actor may manage the student."""
        if model is not None:
            self.check_model(student, model)
        if lesson is not None:
            try:
                lesson = validate_lesson(lesson, licence_confirmed)
            except InvalidLessonError as error:
                raise ChatRefusedError(400, str(error)) from error
        if len(self._store.list_conversations(student.id)) >= MAX_CHATS_PER_STUDENT:
            raise ChatRefusedError(
                409,
                f"{student.display_name} already has {MAX_CHATS_PER_STUDENT} chats. "
                "Delete one first.",
            )
        now = self._clock()
        conversation = Conversation(
            id=uuid.uuid4().hex,
            user_id=student.id,
            title=lesson.title if lesson else "",
            lesson=lesson,
            model=model,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        self._store.save_conversation(conversation)
        return conversation

    def delete_chat(self, student_id: str, conversation_id: str) -> Conversation:
        conversation = self._store.get_conversation(student_id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        self._store.delete_conversation(student_id, conversation_id)
        return conversation

    def set_support(
        self, student_id: str, conversation_id: str, support: SupportLevel
    ) -> Conversation:
        conversation = self._store.get_conversation(student_id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        if conversation.lesson is None:
            raise ChatRefusedError(400, "Only lesson chats have a support level.")

        def apply(current: Conversation) -> None:
            if current.lesson:
                current.lesson.support = support

        return self._store.update_conversation(student_id, conversation_id, apply)

    def set_model(self, owner: User, conversation_id: str, model: str) -> Conversation:
        self.check_model(owner, model)
        if self._store.get_conversation(owner.id, conversation_id) is None:
            raise ConversationNotFoundError()

        def apply(current: Conversation) -> None:
            current.model = model

        return self._store.update_conversation(owner.id, conversation_id, apply)

    def extract_worksheet(self, tutor: User, text: str) -> Worksheet:
        """Questions and worked examples from worksheet text, for the tutor to review.

        Worksheets are tutor content, not student data, so the tutor's preferred model may be
        one that isn't approved for student conversations.
        """
        try:
            messages = extraction_request(text)
        except WorksheetError as error:
            raise ChatRefusedError(400, str(error)) from error
        engine = self._models.get(tutor.preferred_model or "", self._default)
        reply = self._tutor_task(tutor, messages, engine, EXTRACT_OUTPUT_TOKENS, "extraction")
        try:
            return parse_worksheet(reply)
        except WorksheetError as error:
            raise ChatRefusedError(502, str(error)) from error

    def draft_lesson(self, tutor: User, description: str) -> LessonDraft:
        """A lesson's title, topics, notes and support level from the tutor's description.

        A description is usually about a student, so it only goes to a model approved for
        student conversations: the tutor's preferred one if it is, otherwise the default.
        """
        try:
            messages = draft_request(description)
        except DraftError as error:
            raise ChatRefusedError(400, str(error)) from error
        engine = self._models.get(tutor.preferred_model or "", self._default)
        if not engine.profile.approved_for_student_conversations:
            engine = self._default
        reply = self._tutor_task(tutor, messages, engine, DRAFT_OUTPUT_TOKENS, "lesson draft")
        try:
            return parse_draft(reply)
        except DraftError as error:
            raise ChatRefusedError(502, str(error)) from error

    def _tutor_task(
        self,
        tutor: User,
        messages: list[PromptMessage],
        engine: AvailableModel,
        max_output_tokens: int,
        task: str,
    ) -> str:
        """One model call for a tutor's lesson setup, outside any chat, charged to the tutor."""
        if not self._limits.enabled:
            raise ChatRefusedError(503, "Chat is switched off at the moment.")
        self._check_budgets(tutor)
        wait_reason = self._limiter.try_acquire(tutor.id)
        if wait_reason:
            raise ChatRefusedError(429, wait_reason)
        try:
            reply, usage = self._complete(messages, engine, max_output_tokens)
        except ContentFilteredError as error:
            raise ChatRefusedError(400, "The content filter blocked that text.") from error
        except ModelRateLimitedError as error:
            raise ChatRefusedError(429, BUSY) from error
        except Exception as error:
            logger.exception("A %s failed for tutor %s", task, tutor.id)
            raise ChatRefusedError(503, UNAVAILABLE) from error
        finally:
            self._limiter.release(tutor.id)
        try:
            self._charge(tutor, usage, engine.profile)
        except Exception:
            logger.exception("Charging a %s failed for tutor %s", task, tutor.id)
        return reply

    def submit_answer(
        self,
        owner: User,
        conversation_id: str,
        question_number: str,
        working: list[str],
        answer: str,
    ) -> CheckResult:
        """A verdict on the working and final answer; never the answer. Recorded for the tutor."""
        answer = answer.strip()
        if not answer:
            raise ChatRefusedError(400, "Type your final answer first.")
        if len(answer) > MAX_ANSWER_CHARS:
            raise ChatRefusedError(400, f"Keep your answer under {MAX_ANSWER_CHARS} characters.")
        steps = self._steps(working)
        problem = missing_working(steps, answer)
        if problem:
            raise ChatRefusedError(400, problem)
        conversation = self.get_conversation(owner, conversation_id)
        question = self._question(conversation, question_number)
        first_step = shown_first_step(conversation.lesson, question)
        reply = self._student_task(
            owner,
            conversation,
            mark_request(question, steps, answer, first_step),
            "\n".join([*steps, answer]),
        )
        try:
            verdict, feedback = parse_mark(reply)
        except CheckError as error:
            raise ChatRefusedError(502, str(error)) from error
        key = question.answer
        # The answer is right, so at worst the working is what's missing.
        if key and matches_key(answer, key) and verdict in ("slip", "not_yet"):
            verdict, feedback = "show_working", FEEDBACK["show_working"]
        if key and verdict != "correct" and leaks_key(feedback, key):
            feedback = FEEDBACK[verdict]
        now = self._clock()
        attempt = Attempt(
            question=question.number,
            working=steps,
            answer=answer,
            correct=verdict == "correct",
            verdict=verdict,
            verified=bool(key),
            at=now,
        )
        content = (
            f"My working for {question.number}:\n\n{working_message(steps)}\n\n"
            f"**My answer:** {answer}"
        )
        saved = self._record_exchange(owner, conversation_id, question, content, feedback, attempt)
        return CheckResult(verdict, feedback, saved)

    def check_working(
        self, owner: User, conversation_id: str, question_number: str, working: list[str]
    ) -> WorkingFeedback:
        """A hint on unfinished working: on track, or the first step to look at. Not marked."""
        steps = self._steps(working)
        if not steps:
            raise ChatRefusedError(400, "Write at least one step first.")
        conversation = self.get_conversation(owner, conversation_id)
        question = self._question(conversation, question_number)
        first_step = shown_first_step(conversation.lesson, question)
        reply = self._student_task(
            owner,
            conversation,
            working_check_request(question, steps, first_step),
            "\n".join(steps),
        )
        try:
            feedback = parse_working_check(reply)
        except CheckError as error:
            raise ChatRefusedError(502, str(error)) from error
        if question.answer and leaks_key(feedback, question.answer):
            feedback = KEEP_GOING
        content = f"Can you check my working so far?\n\n{working_message(steps)}"
        saved = self._record_exchange(owner, conversation_id, question, content, feedback)
        return WorkingFeedback(feedback, saved)

    def solve_questions(self, tutor: User, questions: list[QuestionToSolve]) -> list[SolvedAnswer]:
        """Final answers for questions without a key, for the tutor to confirm before saving.

        Questions are tutor content, so the tutor's preferred model may be unapproved.
        """
        try:
            messages = solve_request(questions)
        except AnswersError as error:
            raise ChatRefusedError(400, str(error)) from error
        engine = self._models.get(tutor.preferred_model or "", self._default)
        reply = self._tutor_task(tutor, messages, engine, SOLVE_OUTPUT_TOKENS, "solve")
        try:
            return parse_answers(reply, [q.number for q in questions if q.text.strip()])
        except AnswersError as error:
            raise ChatRefusedError(502, str(error)) from error

    def draft_first_steps(self, tutor: User, questions: list[QuestionToStart]) -> list[FirstStep]:
        """A first line of working per question, for the tutor to confirm before saving.

        Questions are tutor content, so the tutor's preferred model may be unapproved.
        """
        try:
            messages = first_steps_request(questions)
        except FirstStepsError as error:
            raise ChatRefusedError(400, str(error)) from error
        engine = self._models.get(tutor.preferred_model or "", self._default)
        reply = self._tutor_task(tutor, messages, engine, FIRST_STEPS_OUTPUT_TOKENS, "first steps")
        try:
            return parse_first_steps(reply, questions)
        except FirstStepsError as error:
            raise ChatRefusedError(502, str(error)) from error

    @staticmethod
    def _steps(working: list[str]) -> list[str]:
        try:
            return tidy_working(working)
        except CheckError as error:
            raise ChatRefusedError(400, str(error)) from error

    @staticmethod
    def _question(conversation: Conversation, number: str) -> Question:
        question = find_question(conversation, number)
        if question is None:
            raise ChatRefusedError(404, "Question not found.")
        return question

    def _student_task(
        self,
        owner: User,
        conversation: Conversation,
        messages: list[PromptMessage],
        student_text: str,
    ) -> str:
        """One model call about a question in the owner's chat, on its approved model."""
        if not self._limits.enabled:
            raise ChatRefusedError(503, "Chat is switched off at the moment.")
        engine = self._engine_for(owner, conversation)
        self._check_budgets(owner)
        wait_reason = self._limiter.try_acquire(owner.id)
        if wait_reason:
            raise ChatRefusedError(429, wait_reason)
        try:
            reply, usage = self._complete(messages, engine, CHECK_OUTPUT_TOKENS)
        except ContentFilteredError as error:
            flag = Flag(kind="content_filter", message=student_text, at=self._clock())
            try:
                self._store.update_conversation(
                    owner.id, conversation.id, lambda c: c.flags.append(flag)
                )
            except Exception:
                logger.exception("Recording a content filter flag failed for %s", conversation.id)
            raise ChatRefusedError(400, FILTERED) from error
        except ModelRateLimitedError as error:
            raise ChatRefusedError(429, BUSY) from error
        except Exception as error:
            logger.exception("Checking working failed for conversation %s", conversation.id)
            raise ChatRefusedError(503, UNAVAILABLE) from error
        finally:
            self._limiter.release(owner.id)
        try:
            self._charge(owner, usage, engine.profile)
        except Exception:
            logger.exception("Charging a working check failed for %s", conversation.id)
        return reply

    def _record_exchange(
        self,
        owner: User,
        conversation_id: str,
        question: Question,
        content: str,
        feedback: str,
        attempt: Attempt | None = None,
    ) -> Conversation:
        """A submission (with its attempt) or a working check, tagged with its question."""
        now = self._clock()
        marked = attempt is not None
        exchange = [
            ChatMessage(
                role="user",
                content=content,
                at=now,
                author=author_of(owner),
                author_name=owner.display_name,
                question=question.number,
                checks_answer=marked,
            ),
            ChatMessage(
                role="assistant",
                content=feedback,
                at=now,
                question=question.number,
                checks_answer=marked,
            ),
        ]

        def record(current: Conversation) -> None:
            current.messages.extend(exchange)
            if attempt is not None:
                current.attempts.append(attempt)
            current.updated_at = now

        try:
            return self._store.update_conversation(owner.id, conversation_id, record)
        except Exception as error:
            logger.exception("Saving a working check failed for conversation %s", conversation_id)
            raise ChatRefusedError(503, UNAVAILABLE) from error

    def get_conversation(self, user: User, conversation_id: str) -> Conversation:
        conversation = self._store.get_conversation(user.id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation

    def begin_turn(
        self,
        sender: User,
        owner: User,
        conversation_id: str,
        content: str,
        to_tutor: bool = False,
        question: str | None = None,
    ) -> Turn:
        """Run every check that can refuse a message, before any model call.

        The caller has checked that the sender may write in the owner's chat.
        """
        content = content.strip()
        if not content:
            raise ChatRefusedError(400, "Type a message first.")
        if len(content) > MAX_INPUT_CHARS:
            raise ChatRefusedError(
                400, f"That message is too long. Keep it under {MAX_INPUT_CHARS} characters."
            )
        conversation = self.get_conversation(owner, conversation_id)
        if len(conversation.messages) >= MAX_MESSAGES_PER_CONVERSATION:
            raise ChatRefusedError(409, "This chat is full. Start a new one.")
        current = find_question(conversation, question)
        message = ChatMessage(
            role="user",
            content=content,
            at=self._clock(),
            author=author_of(sender),
            author_name=sender.display_name,
            question=current.number if current else None,
        )
        context = None
        engine = None
        if asks_ai(conversation, content, message.author or "student", to_tutor, author_of(owner)):
            if not self._limits.enabled:
                raise ChatRefusedError(503, "Chat is switched off at the moment.")
            engine = self._engine_for(owner, conversation)
            self._check_budgets(sender)
            context = self._assemble(owner, conversation, message)
        wait_reason = self._limiter.try_acquire(sender.id)
        if wait_reason:
            raise ChatRefusedError(429, wait_reason)
        return Turn(sender, owner, conversation, message, context, engine)

    def run_turn(self, turn: Turn) -> Iterator[ChatEvent]:
        try:
            if turn.context is None or turn.engine is None:
                yield from self._save_message(turn)
            else:
                yield from self._run_turn(turn, turn.context, turn.engine)
        finally:
            self._limiter.release(turn.sender.id)

    def conversation_version(self, owner: User, conversation_id: str) -> datetime:
        version = self._store.conversation_version(owner.id, conversation_id)
        if version is None:
            raise ConversationNotFoundError()
        return version

    def _engine_for(self, owner: User, conversation: Conversation) -> AvailableModel:
        """The chat's model, a tutor's preferred one for their own chats, or the default.

        A student's chat only ever runs on an approved model: fail closed otherwise.
        """
        model_id = conversation.model or (
            owner.preferred_model if owner.role == Role.TUTOR else None
        )
        engine = self._models.get(model_id or "", self._default)
        if owner.role == Role.STUDENT and not engine.profile.approved_for_student_conversations:
            logger.error("Unapproved model %s on student chat %s", model_id, conversation.id)
            raise ChatRefusedError(503, UNAVAILABLE)
        return engine

    def _assemble(
        self, owner: User, conversation: Conversation, message: ChatMessage
    ) -> AssembledContext:
        try:
            # The owner's profile and their tutor's style, whoever is asking.
            layers = load_profile_layers(owner, self._profiles)
            lesson = conversation.lesson
            return assemble(
                ContextInput(
                    message=message.content,
                    message_author=message.author or author_of(owner),
                    message_author_name=message.author_name,
                    owner_author=author_of(owner),
                    owner_name=owner.display_name,
                    teaching_style=layers.teaching_style,
                    profile=layers.profile,
                    support=SUPPORT_PROMPTS[lesson.support] if lesson else None,
                    lesson=render_lesson(lesson) if lesson else None,
                    summary=conversation.summary,
                    history=conversation.messages,
                    references=[question_reference(q, shown_first_step(lesson, q))]
                    if (q := find_question(conversation, message.question))
                    else [],
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

    def _save_message(self, turn: Turn) -> Iterator[ChatEvent]:
        now = self._clock()

        def append(conversation: Conversation) -> None:
            conversation.messages.append(turn.message)
            conversation.title = conversation.title or turn.message.content[:TITLE_CHARS]
            conversation.updated_at = now

        try:
            saved = self._store.update_conversation(turn.owner.id, turn.conversation.id, append)
        except Exception:
            logger.exception("Saving a message failed for conversation %s", turn.conversation.id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return
        yield ChatEvent("done", {"title": saved.title, "ai": False})

    def _run_turn(
        self, turn: Turn, context: AssembledContext, engine: AvailableModel
    ) -> Iterator[ChatEvent]:
        conversation_id = turn.conversation.id
        profile = engine.profile
        reply: list[str] = []
        usage: Usage | None = None
        try:
            for item in engine.model.stream(context.messages, profile.max_output_tokens):
                if isinstance(item, Usage):
                    usage = item
                else:
                    reply.append(item)
                    yield ChatEvent("delta", {"text": item})
        except ContentFilteredError:
            self._record_filter_hit(turn)
            yield ChatEvent("error", {"message": FILTERED})
            return
        except ModelRateLimitedError:
            logger.warning("Model rate limit hit for conversation %s", conversation_id)
            yield ChatEvent("error", {"message": BUSY})
            return
        except Exception:
            logger.exception("Chat turn failed for conversation %s", conversation_id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return

        now = self._clock()
        ledger = TurnContext(layers=context.layers, estimated_input=context.estimated_input)
        if usage:
            ledger = ledger.model_copy(
                update={
                    "input_tokens": usage.input_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_micro_usd": profile.cost_micro_usd(usage),
                }
            )
            logger.info(
                "Context for %s: estimated %d tokens, reported %d (%d cached)",
                conversation_id,
                ledger.estimated_input,
                usage.input_tokens,
                usage.cached_input_tokens,
            )
        answer = ChatMessage(
            role="assistant",
            content="".join(reply),
            at=now,
            context=ledger,
            question=turn.message.question,
        )

        def append(conversation: Conversation) -> None:
            conversation.messages.extend([turn.message, answer])
            conversation.title = conversation.title or turn.message.content[:TITLE_CHARS]
            conversation.updated_at = now
            add_tokens(conversation, usage)

        try:
            saved = self._store.update_conversation(turn.owner.id, conversation_id, append)
            self._charge(turn.sender, usage, profile)
        except Exception:
            logger.exception("Saving chat turn failed for conversation %s", conversation_id)
            yield ChatEvent("error", {"message": UNAVAILABLE})
            return
        self._summarise_if_due(turn.sender, turn.owner, saved, engine)
        yield ChatEvent("done", {"title": saved.title, "ai": True})

    def _charge(self, user: User, usage: Usage | None, profile: ModelProfile) -> None:
        if usage:
            day = self._clock().date()
            self._store.add_usage(user.id, day, usage.total, profile.cost_micro_usd(usage))

    def _summarise_if_due(
        self, sender: User, owner: User, conversation: Conversation, engine: AvailableModel
    ) -> None:
        """Fold old messages into the summary. A failure is retried on the next turn."""
        batch = messages_to_summarise(conversation)
        if not batch:
            return
        try:
            if self._store.cost_used_by_everyone(self._clock().date()) >= (
                self._limits.daily_global_usd * MICRO_USD
            ):
                return
            text, usage = self._complete(summary_request(conversation.summary, batch), engine)
            summary = clip_summary(text)
            if not summary:
                logger.warning("Empty summary for conversation %s", conversation.id)
            summarised_before = conversation.summarised_count

            def apply(current: Conversation) -> None:
                # Skip if another turn summarised these messages first.
                if summary and current.summarised_count == summarised_before:
                    current.summary = summary
                    current.summarised_count += len(batch)
                add_tokens(current, usage)

            self._store.update_conversation(owner.id, conversation.id, apply)
            self._charge(sender, usage, engine.profile)
        except Exception:
            logger.exception("Summarising failed for conversation %s", conversation.id)

    def _complete(
        self,
        messages: Sequence[PromptMessage],
        engine: AvailableModel,
        max_output_tokens: int = SUMMARY_OUTPUT_TOKENS,
    ) -> tuple[str, Usage | None]:
        parts: list[str] = []
        usage: Usage | None = None
        for item in engine.model.stream(messages, max_output_tokens):
            if isinstance(item, Usage):
                usage = item
            else:
                parts.append(item)
        return "".join(parts), usage

    def _record_filter_hit(self, turn: Turn) -> None:
        flag = Flag(kind="content_filter", message=turn.message.content, at=turn.message.at)
        try:
            self._store.update_conversation(
                turn.owner.id, turn.conversation.id, lambda c: c.flags.append(flag)
            )
        except Exception:
            logger.exception("Recording a content filter flag failed for %s", turn.conversation.id)


def add_tokens(conversation: Conversation, usage: Usage | None) -> None:
    if usage:
        conversation.input_tokens += usage.input_tokens
        conversation.output_tokens += usage.output_tokens
