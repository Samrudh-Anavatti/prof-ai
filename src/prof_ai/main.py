from pathlib import Path

from fastapi import APIRouter, FastAPI

from prof_ai.auth import CurrentUser
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

    return api


def create_app(
    settings: Settings | None = None,
    user_repository: UserRepository | None = None,
    static_dir: Path = STATIC_DIR,
) -> FastAPI:
    settings = settings or load_settings()
    settings.validate()
    if user_repository is None and settings.cosmos_endpoint:
        from prof_ai.users.cosmos_repository import CosmosUserRepository

        user_repository = CosmosUserRepository(settings.cosmos_endpoint)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Prof AI",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    app.state.user_repository = user_repository

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_api_router())
    mount_frontend(app, static_dir)
    return app


app = create_app()
