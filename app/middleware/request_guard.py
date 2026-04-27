"""Reject oversized request bodies and unsupported content types.

Runs before route handlers for write methods (POST/PUT/PATCH). Returns a
plain JSON error response directly because BaseHTTPMiddleware does not
propagate raised exceptions back through FastAPI's exception handlers.
"""

from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


_GUARDED_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "status_code": status_code,
            },
        },
    )


class RequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        max_body_bytes: int,
        allowed_content_types: Iterable[str],
    ):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.allowed_content_types = tuple(t.strip().lower() for t in allowed_content_types)

    async def dispatch(self, request: Request, call_next):
        if request.method not in _GUARDED_METHODS:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return _error(400, "BAD_REQUEST", "Invalid Content-Length header")
            if length > self.max_body_bytes:
                return _error(
                    413,
                    "PAYLOAD_TOO_LARGE",
                    f"Request body exceeds the {self.max_body_bytes}-byte limit",
                )

        content_type = request.headers.get("content-type")
        if content_type:
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type and media_type not in self.allowed_content_types:
                return _error(
                    415,
                    "UNSUPPORTED_MEDIA_TYPE",
                    f"Unsupported content type: {media_type}",
                )

        return await call_next(request)
