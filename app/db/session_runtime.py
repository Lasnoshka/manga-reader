from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base


engine = None
AsyncSessionLocal = None


def init_engine():
    """Initialize the SQLAlchemy engine and session factory."""
    global engine, AsyncSessionLocal

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
    )

    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db():
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def db_ping() -> bool:
    """Lightweight, silent DB readiness check."""
    if engine is None:
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def test_connection() -> bool:
    """Test the database connection."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("PostgreSQL connection successful")
            return True
    except Exception as exc:
        print(f"PostgreSQL connection failed: {exc}")
        return False


async def init_db():
    """Initialize database connection and create tables for local development."""
    init_engine()

    if not await test_connection():
        print("Skipping table creation because the database connection failed")
        return

    try:
        async with engine.begin() as conn:
            from app.db.models import (  # noqa: F401
                bookmark,
                chapter,
                comment,
                genre,
                like,
                manga,
                page,
                reading_progress,
                user,
            )

            await conn.run_sync(Base.metadata.create_all)
            print("Database tables created or verified successfully")
    except Exception as exc:
        print(f"Error while creating tables: {exc}")


async def close_db():
    """Close database connections."""
    if engine:
        await engine.dispose()
        print("Database connection closed")
