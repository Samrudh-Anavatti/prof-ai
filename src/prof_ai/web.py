from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent / "static"

# style-src-attr: MathLive positions maths with inline style attributes (ADR 0003 amendment).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)
RESERVED_PREFIXES = ("api", "assets", "docs")
SHELL_HEADERS = {"Content-Security-Policy": CONTENT_SECURITY_POLICY, "Cache-Control": "no-cache"}

NOT_BUILT_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Prof AI</title></head>
<body><main><h1>Prof AI</h1>
<p>The frontend isn't built. Run <code>npm run build</code> in <code>web/</code>.</p>
</main></body>
</html>"""


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA: hashed assets, then index.html for every non-API GET."""
    index_file = static_dir / "index.html"
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def app_shell(path: str) -> Response:
        first_segment, _, _ = path.partition("/")
        if first_segment in RESERVED_PREFIXES or "." in path.rsplit("/", 1)[-1]:
            raise HTTPException(404, "Not found.")
        if not index_file.is_file():
            return HTMLResponse(NOT_BUILT_PAGE, headers=SHELL_HEADERS)
        return FileResponse(index_file, media_type="text/html", headers=SHELL_HEADERS)
