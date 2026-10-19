from collections.abc import Awaitable, Callable, Mapping

from fastapi import Request, Response
from fastapi.responses import JSONResponse

DEFAULT_MAX_BODY_BYTES = 1024 * 1024
BODY_METHODS = {"POST", "PUT", "PATCH"}

Handler = Callable[[Request], Awaitable[Response]]


def body_size_limit(
    overrides: Mapping[str, int],
) -> Callable[[Request, Handler], Awaitable[Response]]:
    """Refuse oversized bodies from the Content-Length header, before anything reads them."""

    async def middleware(request: Request, call_next: Handler) -> Response:
        if request.method in BODY_METHODS and request.url.path.startswith("/api/"):
            limit = overrides.get(request.url.path, DEFAULT_MAX_BODY_BYTES)
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return JSONResponse({"detail": "Send a Content-Length header."}, status_code=411)
            if int(length) > limit:
                return JSONResponse({"detail": "That upload is too large."}, status_code=413)
        return await call_next(request)

    return middleware
