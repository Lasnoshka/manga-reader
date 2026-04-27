"""Lightweight Redis-backed rate limiter for FastAPI dependencies.

Counts requests per (key, client identifier) inside a rolling window
implemented as a Redis counter with TTL. Falls open if Redis is disabled or
unreachable so cache outages don't lock users out.

When the app is deployed behind a reverse proxy, request.client.host will
report the proxy's address and every caller will share the same bucket.
Trusted X-Forwarded-For handling should be configured before relying on
this limiter for production abuse protection.
"""

from fastapi import Request

from app.cache import client as cache_client
from app.core.exceptions import RateLimitError
from app.core.logger import logger


class RateLimiter:
    def __init__(self, *, key: str, max_requests: int, window_seconds: int):
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    @staticmethod
    def _client_id(request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def __call__(self, request: Request) -> None:
        redis = cache_client.redis_client
        if redis is None:
            return

        bucket = f"ratelimit:{self.key}:{self._client_id(request)}"
        try:
            current = await redis.incr(bucket)
            if current == 1:
                await redis.expire(bucket, self.window_seconds)
            if current > self.max_requests:
                retry_after = await redis.ttl(bucket)
                raise RateLimitError(retry_after=max(retry_after, 1))
        except RateLimitError:
            raise
        except Exception as exc:
            logger.warning(f"Rate limit check failed for {bucket}: {exc}")
