import inspect
import logging
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Callable

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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
        handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        return handler

    def _setup_handler(self) -> None:
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)

        self.logger.addHandler(self._get_file_handler())

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
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
