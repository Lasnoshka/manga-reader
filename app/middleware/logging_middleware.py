import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import api_logger, request_id_var


REQUEST_ID_HEADER = "X-Request-ID"


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request/response and propagates a correlation ID."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start_time = time.time()

        try:
            client_host = request.client.host if request.client else "unknown"
            query_str = str(request.query_params) if request.query_params else ""
            api_logger.info(
                f"-> {request.method} {request.url.path}",
                extra={
                    "event": "http.request",
                    "client": client_host,
                    "query": query_str,
                },
            )

            response = await call_next(request)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            api_logger.info(
                f"<- {request.method} {request.url.path}",
                extra={
                    "event": "http.response",
                    "status": response.status_code,
                    "duration_ms": elapsed_ms,
                },
            )

            response.headers[REQUEST_ID_HEADER] = rid
            return response
        finally:
            request_id_var.reset(token)
