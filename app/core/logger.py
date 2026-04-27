import contextvars
import inspect
import json
import logging
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Callable, Optional

from app.core.datetime_utils import utcnow

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_TEXT_LOG_PATTERN = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


_RESERVED_RECORD_KEYS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render log records as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": f"{record.filename}:{record.lineno}",
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _build_formatter() -> logging.Formatter:
    # Local import to avoid a circular import at module load time.
    from app.config import settings

    if settings.LOG_FORMAT == "json":
        return JsonFormatter()
    return logging.Formatter(_TEXT_LOG_PATTERN, _DATE_FORMAT)


class DailyRotatingLogger:
    def __init__(self, name: str = "manga_api", level: int = logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False
        self.current_date = datetime.now().strftime("%Y_%m_%d")
        self._setup_handler()

    def _get_file_handler(self) -> logging.Handler:
        current_file = LOG_DIR / f"Logs_{self.current_date}.log"
        handler = logging.FileHandler(current_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(_build_formatter())
        return handler

    def _setup_handler(self) -> None:
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)

        self.logger.addHandler(self._get_file_handler())

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(_build_formatter())
        self.logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        new_date = datetime.now().strftime("%Y_%m_%d")
        if new_date != self.current_date:
            self.current_date = new_date
            self._setup_handler()
        return self.logger


_main_logger = DailyRotatingLogger("manga_api")
logger = _main_logger.get_logger()

_db_logger = DailyRotatingLogger("manga_api.db")
db_logger = _db_logger.get_logger()

_api_logger = DailyRotatingLogger("manga_api.api")
api_logger = _api_logger.get_logger()


def log_execution(logger_to_use: logging.Logger, level: int = logging.DEBUG):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger_to_use.log(level, f"START {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                logger_to_use.log(level, f"OK {func.__name__} | {elapsed:.2f}ms")
                return result
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                logger_to_use.error(
                    f"FAIL {func.__name__} | {type(exc).__name__}: {exc} | {elapsed:.2f}ms"
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger_to_use.log(level, f"START {func.__name__}")
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                logger_to_use.log(level, f"OK {func.__name__} | {elapsed:.2f}ms")
                return result
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                logger_to_use.error(
                    f"FAIL {func.__name__} | {type(exc).__name__}: {exc} | {elapsed:.2f}ms"
                )
                raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def log_api_call(func: Callable) -> Callable:
    return log_execution(api_logger, logging.INFO)(func)
