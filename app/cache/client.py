import json
from typing import Any, Optional

try:
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # pragma: no cover - fallback for incomplete local env
    Redis = None

    class RedisError(Exception):
        pass

from app.config import settings
from app.core.logger import logger


redis_client: Optional[Redis] = None


async def init_cache() -> None:
    global redis_client

    if Redis is None:
        logger.warning("redis package is not installed, cache disabled")
        redis_client = None
        return

    redis_client = Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

    try:
        await redis_client.ping()
        logger.info("Redis cache connected")
    except RedisError as exc:
        logger.warning(f"Redis is unavailable, cache disabled: {exc}")
        redis_client = None


async def cache_ping() -> Optional[bool]:
    """True if Redis responds, False on error, None if cache is disabled."""
    if redis_client is None:
        return None
    try:
        await redis_client.ping()
        return True
    except RedisError:
        return False


async def close_cache() -> None:
    global redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis cache connection closed")


async def get_json(key: str) -> Any:
    if redis_client is None:
        return None

    try:
        value = await redis_client.get(key)
        return json.loads(value) if value is not None else None
    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning(f"Failed to read cache key '{key}': {exc}")
        return None


async def set_json(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    if redis_client is None:
        return False

    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl)
        return True
    except (RedisError, TypeError) as exc:
        logger.warning(f"Failed to write cache key '{key}': {exc}")
        return False


async def delete_pattern(pattern: str) -> int:
    if redis_client is None:
        return 0

    deleted = 0
    try:
        async for key in redis_client.scan_iter(match=pattern):
            deleted += await redis_client.delete(key)
        return deleted
    except RedisError as exc:
        logger.warning(f"Failed to delete cache pattern '{pattern}': {exc}")
        return 0


async def increment_sorted_set(key: str, member: str, amount: int = 1) -> None:
    if redis_client is None:
        return

    try:
        await redis_client.zincrby(key, amount, member)
    except RedisError as exc:
        logger.warning(f"Failed to increment Redis sorted set '{key}': {exc}")


async def get_sorted_set_desc(key: str, start: int = 0, stop: int = -1, with_scores: bool = False):
    if redis_client is None:
        return []

    try:
        return await redis_client.zrevrange(key, start, stop, withscores=with_scores)
    except RedisError as exc:
        logger.warning(f"Failed to read Redis sorted set '{key}': {exc}")
        return []
