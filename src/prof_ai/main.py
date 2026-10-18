from pathlib import Path

from fastapi import APIRouter, FastAPI

from prof_ai.auth import CurrentUser
from prof_ai.chat.api import create_chat_router
from prof_ai.chat.service import ChatLimits, ChatService
from prof_ai.config import Settings, load_settings
from prof_ai.users.repository import UserRepository
from prof_ai.web import STATIC_DIR, mount_frontend


def create_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")

    @api.get("/me")
    def me(user: CurrentUser) -> dict[str, str]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
        }

    api.include_router(create_chat_router())
    return api


def chat_limits(settings: Settings) -> ChatLimits:
    return ChatLimits(
        enabled=settings.chat_enabled,
        daily_user_tokens=settings.chat_daily_user_tokens,
        daily_global_tokens=settings.chat_daily_global_tokens,
    )


def azure_chat_service(settings: Settings) -> ChatService | None:
    if not (
        settings.foundry_endpoint and settings.cosmos_endpoint and settings.storage_account_url
    ):
        return None
    from prof_ai.chat.cosmos_store import CosmosChatStore
    from prof_ai.chat.model import FoundryChatModel
    from prof_ai.content.azure_backend import AzureBlobBackend
    from prof_ai.profiles.store import ProfileStore

    return ChatService(
        FoundryChatModel(settings.foundry_endpoint, settings.chat_deployment),
        CosmosChatStore(settings.cosmos_endpoint),
        ProfileStore(AzureBlobBackend(settings.storage_account_url)),
        chat_limits(settings),
    )


def create_app(
    settings: Settings | None = None,
    user_repository: UserRepository | None = None,
    chat_service: ChatService | None = None,
    static_dir: Path = STATIC_DIR,
) -> FastAPI:
    settings = settings or load_settings()
    settings.validate()
    if user_repository is None and settings.cosmos_endpoint:
        from prof_ai.users.cosmos_repository import CosmosUserRepository

        user_repository = CosmosUserRepository(settings.cosmos_endpoint)
    if chat_service is None:
        chat_service = azure_chat_service(settings)

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

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_api_router())
    mount_frontend(app, static_dir)
    return app


app = create_app()
