"""Клиент для отправки задач в ARQ-очередь из FastAPI."""
from typing import Optional

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings
from app.core.logger import logger


_pool: Optional[ArqRedis] = None


async def get_queue() -> Optional[ArqRedis]:
    """Возвращает пул соединений к Redis для ARQ. None если Redis недоступен."""
    global _pool
    if _pool is not None:
        return _pool
    try:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        return _pool
    except Exception as exc:
        logger.warning(f"ARQ queue unavailable: {exc}")
        return None


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
