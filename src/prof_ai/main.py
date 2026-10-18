from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from prof_ai.auth import CurrentUser
from prof_ai.config import Settings, load_settings
from prof_ai.users.repository import UserRepository

LANDING_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prof AI</title></head>
<body><main><h1>Prof AI</h1><p>Coming soon.</p>
<p><a href="/me">My account</a> · <a href="/.auth/logout">Sign out</a></p></main></body>
</html>"""


def create_app(
    settings: Settings | None = None, user_repository: UserRepository | None = None
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

    @app.get("/", response_class=HTMLResponse)
    def landing() -> str:
        return LANDING_PAGE

    @app.get("/me")
    def me(user: CurrentUser) -> dict[str, str]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
        }

    return app


app = create_app()
