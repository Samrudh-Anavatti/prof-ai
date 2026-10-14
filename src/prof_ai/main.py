from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from prof_ai.config import Settings, load_settings

LANDING_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prof AI</title></head>
<body><main><h1>Prof AI</h1><p>Coming soon.</p></main></body>
</html>"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Prof AI",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def landing() -> str:
        return LANDING_PAGE

    return app


app = create_app()
