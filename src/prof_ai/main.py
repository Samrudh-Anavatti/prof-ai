from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, FastAPI

from prof_ai.auth import CurrentUser
from prof_ai.chat.api import create_chat_router
from prof_ai.chat.models_api import create_models_router
from prof_ai.chat.service import AvailableModel, ChatLimits, ChatService
from prof_ai.config import Settings, load_settings
from prof_ai.lessons.api import MAX_EXTRACT_REQUEST_BYTES, create_lessons_router
from prof_ai.profiles.api import create_profiles_router
from prof_ai.profiles.store import ProfileStore
from prof_ai.request_limits import body_size_limit
from prof_ai.users.api import create_users_router
from prof_ai.users.repository import UserRepository
from prof_ai.web import STATIC_DIR, mount_frontend


def create_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")

    @api.get("/me")
    def me(user: CurrentUser) -> dict[str, str | bool]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
            "is_admin": user.is_admin,
        }

    api.include_router(create_chat_router())
    api.include_router(create_profiles_router())
    api.include_router(create_users_router())
    api.include_router(create_lessons_router())
    api.include_router(create_models_router())
    return api


def chat_limits(settings: Settings) -> ChatLimits:
    return ChatLimits(
        enabled=settings.chat_enabled,
        daily_user_usd=settings.chat_daily_user_usd,
        daily_global_usd=settings.chat_daily_global_usd,
    )


def azure_profile_store(settings: Settings) -> ProfileStore | None:
    if not settings.storage_account_url:
        return None
    from prof_ai.content.azure_backend import AzureBlobBackend

    return ProfileStore(AzureBlobBackend(settings.storage_account_url))


def ollama_models(settings: Settings) -> list[AvailableModel]:
    """Ollama Cloud models, when its key is set. They have no per-minute token quota."""
    if not settings.ollama_api_key:
        return []
    from prof_ai.chat.model import ollama_chat_model
    from prof_ai.chat.model_profiles import MODEL_PROFILES

    return [
        AvailableModel(profile, ollama_chat_model(settings.ollama_api_key, profile.deployment))
        for profile in MODEL_PROFILES.values()
        if profile.provider == "ollama"
    ]


def azure_chat_service(settings: Settings, profiles: ProfileStore | None) -> ChatService | None:
    if not (settings.foundry_endpoint and settings.cosmos_endpoint and profiles):
        return None
    from prof_ai.chat.cosmos_store import CosmosChatStore
    from prof_ai.chat.model import foundry_chat_model
    from prof_ai.chat.model_profiles import model_profile

    return ChatService(
        foundry_chat_model(settings.foundry_endpoint, settings.chat_deployment),
        CosmosChatStore(settings.cosmos_endpoint),
        profiles,
        chat_limits(settings),
        model_profile=model_profile(settings.chat_deployment),
        tokens_per_minute=settings.chat_tokens_per_minute,
        extra_models=ollama_models(settings),
    )


def user_data_eraser(
    chat_service: ChatService | None, profile_store: ProfileStore | None
) -> Callable[[str], None] | None:
    if chat_service is None or profile_store is None:
        return None

    def erase(user_id: str) -> None:
        chat_service.erase_user_data(user_id)
        profile_store.delete_all(user_id)

    return erase


def create_app(
    settings: Settings | None = None,
    user_repository: UserRepository | None = None,
    chat_service: ChatService | None = None,
    profile_store: ProfileStore | None = None,
    static_dir: Path = STATIC_DIR,
) -> FastAPI:
    settings = settings or load_settings()
    settings.validate()
    if user_repository is None and settings.cosmos_endpoint:
        from prof_ai.users.cosmos_repository import CosmosUserRepository

        user_repository = CosmosUserRepository(settings.cosmos_endpoint)
    if profile_store is None:
        profile_store = azure_profile_store(settings)
    if chat_service is None:
        chat_service = azure_chat_service(settings, profile_store)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Prof AI",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    app.state.user_repository = user_repository
    app.state.chat_service = chat_service
    app.state.profile_store = profile_store
    app.state.erase_user_data = user_data_eraser(chat_service, profile_store)

    app.middleware("http")(body_size_limit({"/api/lessons/extract": MAX_EXTRACT_REQUEST_BYTES}))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_api_router())
    mount_frontend(app, static_dir)
    return app


app = create_app()
