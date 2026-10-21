import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from prof_ai.auth import require_role
from prof_ai.chat.api import chat_service
from prof_ai.chat.model_profiles import ModelProfile, Provider
from prof_ai.chat.models import Usage
from prof_ai.users.models import AuditEvent, Role, User
from prof_ai.users.repository import UserRepository

Tutor = Annotated[User, Depends(require_role(Role.TUTOR))]
# A lesson turn with a mid-sized prompt and a short reply, uncached: a fair yardstick for
# comparing models, not a promise.
TYPICAL_MESSAGE = Usage(input_tokens=6_000, output_tokens=300)


class ModelOption(BaseModel):
    id: str
    label: str
    provider: Provider
    approved_for_student_conversations: bool
    context_window: int
    input_usd_per_m: float
    cached_input_usd_per_m: float
    output_usd_per_m: float
    typical_message_usd: float
    notes: str


class ModelList(BaseModel):
    models: list[ModelOption]
    default: str
    preferred: str | None


class PreferredModel(BaseModel):
    model: str | None


def model_option(profile: ModelProfile) -> ModelOption:
    return ModelOption(
        id=profile.deployment,
        label=profile.label or profile.deployment,
        provider=profile.provider,
        approved_for_student_conversations=profile.approved_for_student_conversations,
        context_window=profile.context_window,
        input_usd_per_m=profile.input_usd_per_m,
        cached_input_usd_per_m=profile.cached_input_usd_per_m,
        output_usd_per_m=profile.output_usd_per_m,
        typical_message_usd=profile.cost_micro_usd(TYPICAL_MESSAGE) / 1_000_000,
        notes=profile.notes,
    )


def model_list(request: Request, preferred: str | None) -> ModelList:
    service = chat_service(request)
    return ModelList(
        models=[model_option(p) for p in service.models()],
        default=service.default_model.deployment,
        preferred=preferred,
    )


def create_models_router() -> APIRouter:
    router = APIRouter(prefix="/models")

    @router.get("")
    def list_models(tutor: Tutor, request: Request) -> ModelList:
        return model_list(request, tutor.preferred_model)

    @router.put("/preferred")
    def set_preferred_model(body: PreferredModel, tutor: Tutor, request: Request) -> ModelList:
        """The tutor's model for their own test chats; any registered model is allowed."""
        models = {p.deployment for p in chat_service(request).models()}
        if body.model is not None and body.model not in models:
            raise HTTPException(400, "That model isn't available.")
        users: UserRepository = request.app.state.user_repository
        now = datetime.now(UTC)
        try:
            users.save(tutor.model_copy(update={"preferred_model": body.model, "updated_at": now}))
            users.record(
                AuditEvent(
                    id=str(uuid.uuid4()),
                    user_id=tutor.id,
                    action="preferred_model_changed",
                    actor=tutor.email,
                    reason=body.model or "default",
                    at=now,
                )
            )
        except Exception as error:
            raise HTTPException(503, "Couldn't save your model. Try again later.") from error
        return model_list(request, body.model)

    return router
