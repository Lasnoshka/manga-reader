from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from typing import Dict, Any, Optional
from app.core.logger import logger
import traceback
import uuid
from app.core.datetime_utils import utcnow


class AppException(Exception):
    """Базовое кастомное исключение приложения"""
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str = "APP_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


# ========== Кастомные исключения ==========

class Custom501Error(AppException):
    """Кастомная ошибка 501 (зарезервирована)"""
    def __init__(self, message: str = "Custom 501 Error", details: Optional[Dict] = None):
        super().__init__(
            status_code=501,
            message=message,
            error_code="CUSTOM_501",
            details=details
        )


class ResourceNotFoundError(AppException):
    """Ресурс не найден"""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            status_code=404,
            message=f"{resource} with identifier '{identifier}' not found",
            error_code="RESOURCE_NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class ResourceAlreadyExistsError(AppException):
    """Ресурс уже существует"""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            status_code=409,
            message=f"{resource} with identifier '{identifier}' already exists",
            error_code="RESOURCE_ALREADY_EXISTS",
            details={"resource": resource, "identifier": identifier}
        )


class ValidationErrorCustom(AppException):
    """Ошибка валидации данных"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            status_code=422,
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )


class AuthenticationError(AppException):
    """Ошибка аутентификации"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=401,
            message=message,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(AppException):
    """Ошибка авторизации (недостаточно прав)"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            status_code=403,
            message=message,
            error_code="AUTHORIZATION_ERROR"
        )


class BadRequestError(AppException):
    """Неверный запрос"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            status_code=400,
            message=message,
            error_code="BAD_REQUEST",
            details=details
        )


class DatabaseError(AppException):
    """Ошибка базы данных"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            status_code=503,
            message=message,
            error_code="DATABASE_ERROR",
            details=details
        )


class ExternalServiceError(AppException):
    """Ошибка внешнего сервиса"""
    def __init__(self, service: str, message: str):
        super().__init__(
            status_code=502,
            message=f"External service '{service}' error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service}
        )


class RateLimitError(AppException):
    """Превышен лимит запросов"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_ERROR",
            details={"retry_after": retry_after}
        )


# ========== Форматтер ответа ==========

class ErrorResponse:
    """Стандартный формат ответа с ошибкой"""

    @staticmethod
    def create(
        status_code: int,
        message: str,
        error_code: str,
        path: str,
        method: str,
        details: Optional[Dict] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "status_code": status_code,
                "details": details or {}
            },
            "meta": {
                "path": path,
                "method": method,
                "timestamp": utcnow().isoformat() + "Z",
                "trace_id": trace_id
            }
        }


# ========== Глобальный обработчик исключений ==========

def setup_exception_handlers(app: FastAPI) -> None:
    """Регистрирует все обработчики исключений в приложении"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Обработчик кастомных исключений приложения"""
        trace_id = str(uuid.uuid4())[:8]

        logger.warning(
            f"AppException | {exc.status_code} | {exc.error_code} | "
            f"{request.method} {request.url.path} | {exc.message}"
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.create(
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.error_code,
                path=request.url.path,
                method=request.method,
                details=exc.details,
                trace_id=trace_id
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Обработчик стандартных HTTP исключений"""
        trace_id = str(uuid.uuid4())[:8]

        error_codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            408: "REQUEST_TIMEOUT",
            409: "CONFLICT",
            410: "GONE",
            413: "PAYLOAD_TOO_LARGE",
            414: "URI_TOO_LONG",
            415: "UNSUPPORTED_MEDIA_TYPE",
            422: "UNPROCESSABLE_ENTITY",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            501: "NOT_IMPLEMENTED",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT",
        }

        error_code = error_codes.get(exc.status_code, f"HTTP_{exc.status_code}")

        if exc.status_code >= 500:
            logger.error(
                f"HTTPException | {exc.status_code} | {error_code} | "
                f"{request.method} {request.url.path} | {exc.detail}"
            )
        else:
            logger.warning(
                f"HTTPException | {exc.status_code} | {error_code} | "
                f"{request.method} {request.url.path} | {exc.detail}"
            )

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.create(
                status_code=exc.status_code,
                message=str(exc.detail),
                error_code=error_code,
                path=request.url.path,
                method=request.method,
                trace_id=trace_id
            )
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Обработчик ошибок валидации запроса"""
        trace_id = str(uuid.uuid4())[:8]

        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        logger.warning(
            f"ValidationError | 422 | {request.method} {request.url.path} | "
            f"{len(validation_errors)} error(s)"
        )

        return JSONResponse(
            status_code=422,
            content=ErrorResponse.create(
                status_code=422,
                message="Request validation failed",
                error_code="VALIDATION_ERROR",
                path=request.url.path,
                method=request.method,
                details={"validation_errors": validation_errors},
                trace_id=trace_id
            )
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError):
        """Обработчик ошибок валидации Pydantic"""
        trace_id = str(uuid.uuid4())[:8]

        logger.warning(
            f"PydanticValidationError | 422 | {request.method} {request.url.path}"
        )

        return JSONResponse(
            status_code=422,
            content=ErrorResponse.create(
                status_code=422,
                message="Data validation failed",
                error_code="VALIDATION_ERROR",
                path=request.url.path,
                method=request.method,
                details={"errors": exc.errors()},
                trace_id=trace_id
            )
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Глобальный обработчик ВСЕХ необработанных исключений"""
        trace_id = str(uuid.uuid4())[:8]

        if isinstance(exc, ConnectionError):
            status_code = 503
            error_code = "CONNECTION_ERROR"
            message = "Database or service connection failed"
        elif isinstance(exc, TimeoutError):
            status_code = 504
            error_code = "TIMEOUT_ERROR"
            message = "Request timeout"
        elif isinstance(exc, PermissionError):
            status_code = 403
            error_code = "PERMISSION_ERROR"
            message = "Permission denied"
        elif isinstance(exc, FileNotFoundError):
            status_code = 404
            error_code = "FILE_NOT_FOUND"
            message = "Requested file not found"
        elif isinstance(exc, ValueError):
            status_code = 400
            error_code = "VALUE_ERROR"
            message = str(exc)
        elif isinstance(exc, KeyError):
            status_code = 400
            error_code = "KEY_ERROR"
            message = f"Missing required key: {exc}"
        elif isinstance(exc, AttributeError):
            status_code = 500
            error_code = "ATTRIBUTE_ERROR"
            message = "Internal attribute error"
        elif isinstance(exc, TypeError):
            status_code = 400
            error_code = "TYPE_ERROR"
            message = str(exc)
        elif isinstance(exc, NotImplementedError):
            status_code = 501
            error_code = "NOT_IMPLEMENTED"
            message = str(exc) or "Feature not implemented"
        else:
            status_code = 520
            error_code = "UNKNOWN_ERROR"
            message = "An unexpected error occurred"

        logger.error(
            f"UnhandledException | {status_code} | {error_code} | "
            f"{request.method} {request.url.path} | {type(exc).__name__}: {exc}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )

        if status_code == 500:
            status_code = 520
            error_code = "INTERNAL_ERROR_MAPPED"
            message = "Internal server error (mapped to 520)"

        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse.create(
                status_code=status_code,
                message=message,
                error_code=error_code,
                path=request.url.path,
                method=request.method,
                details={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)
                },
                trace_id=trace_id
            )
        )


def handle_exceptions(func):
    """Декоратор для автоматического перехвата и преобразования исключений"""
    from functools import wraps
    import asyncio

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AppException:
            raise
        except StarletteHTTPException:
            raise
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {type(e).__name__}: {e}")
            raise BadRequestError(
                message=f"Operation failed: {str(e)}",
                details={"function": func.__name__, "error_type": type(e).__name__}
            )

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppException:
            raise
        except StarletteHTTPException:
            raise
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {type(e).__name__}: {e}")
            raise BadRequestError(
                message=f"Operation failed: {str(e)}",
                details={"function": func.__name__, "error_type": type(e).__name__}
            )

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
