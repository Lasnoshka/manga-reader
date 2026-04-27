import pytest

import app.cache.client as cache_client
from app.core.exceptions import RateLimitError
from app.core.rate_limit import RateLimiter


class _FakeRedis:
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)


class _FakeRequest:
    def __init__(self, host: str = "1.2.3.4"):
        self.client = type("C", (), {"host": host})()


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache_client, "redis_client", fake)
    return fake


async def test_limiter_passes_when_redis_disabled(monkeypatch):
    monkeypatch.setattr(cache_client, "redis_client", None)
    limiter = RateLimiter(key="t", max_requests=1, window_seconds=60)
    await limiter(_FakeRequest())
    await limiter(_FakeRequest())  # would exceed if redis were on


async def test_limiter_allows_within_threshold(fake_redis):
    limiter = RateLimiter(key="t", max_requests=3, window_seconds=60)
    request = _FakeRequest()
    for _ in range(3):
        await limiter(request)


async def test_limiter_blocks_after_threshold(fake_redis):
    limiter = RateLimiter(key="t", max_requests=2, window_seconds=60)
    request = _FakeRequest()
    await limiter(request)
    await limiter(request)
    with pytest.raises(RateLimitError):
        await limiter(request)


async def test_limiter_separates_by_client(fake_redis):
    limiter = RateLimiter(key="t", max_requests=1, window_seconds=60)
    await limiter(_FakeRequest(host="1.1.1.1"))
    await limiter(_FakeRequest(host="2.2.2.2"))  # different IP, should pass


async def test_limiter_swallows_redis_errors(monkeypatch):
    class _Broken:
        async def incr(self, key):
            raise RuntimeError("redis is down")

    monkeypatch.setattr(cache_client, "redis_client", _Broken())
    limiter = RateLimiter(key="t", max_requests=1, window_seconds=60)
    await limiter(_FakeRequest())  # must not raise
