import os

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 32)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

import app.db.session_runtime as session_runtime  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402, F401
    bookmark, chapter, comment, genre, like, manga, page, reading_progress, user,
)
from app.db.session_runtime import get_db  # noqa: E402
from app.main import app  # noqa: E402


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DB_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    session_runtime.AsyncSessionLocal = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_token(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "tr0ub4dor&3",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client, session_factory):
    r = await client.post("/api/v1/auth/register", json={
        "username": "boss",
        "email": "boss@example.com",
        "password": "tr0ub4dor&3",
    })
    assert r.status_code == 201, r.text
    # Повышаем до admin напрямую в БД
    from sqlalchemy import update
    from app.db.models.user import User
    async with session_factory() as s:
        await s.execute(update(User).where(User.username == "boss").values(role="admin"))
        await s.commit()
    return r.json()["access_token"]


@pytest.fixture
def auth_header():
    def _h(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _h
