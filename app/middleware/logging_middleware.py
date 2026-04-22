import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import api_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех HTTP запросов/ответов (АОП)"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Логируем входящий запрос
        query_str = str(request.query_params) if request.query_params else ""
        api_logger.info(
            f"-> {request.method} {request.url.path} | "
            f"Client: {request.client.host} | "
            f"Query: {query_str}"
        )

        # Выполняем запрос
        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        api_logger.info(
            f"<- {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Time: {process_time:.2f}ms"
        )

        return response
