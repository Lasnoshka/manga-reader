"""ARQ worker: фоновая обработка задач.

Запуск: `arq app.tasks.worker.WorkerSettings`
"""
from arq.connections import RedisSettings
from sqlalchemy import select

from app.cache.client import delete_pattern
from app.config import settings
from app.core.logger import logger
from app.db.models.manga import Manga
from app.db.session_runtime import AsyncSessionLocal, init_engine
from app.services.rating_service import recompute_manga_rating


async def startup(ctx):
    init_engine()
    logger.info("ARQ worker started")


async def shutdown(ctx):
    logger.info("ARQ worker stopped")


async def recalculate_manga_rating(ctx, manga_id: int) -> dict:
    """Recompute Manga.rating / rating_count from the manga_ratings table."""
    async with AsyncSessionLocal() as session:
        summary = await recompute_manga_rating(session, manga_id)
        if not summary["found"]:
            logger.warning(f"recalculate_manga_rating: manga {manga_id} not found")
            return {"manga_id": manga_id, "status": "not_found"}
        await session.commit()

    await delete_pattern(f"manga:detail:{manga_id}")
    await delete_pattern("manga:list:*")
    logger.info(
        f"recalculate_manga_rating: manga={manga_id} avg={summary['average']} count={summary['count']}"
    )
    return summary


async def recalculate_all_ratings(ctx) -> dict:
    """Крон-задача: пробегает по всем тайтлам и ставит новые рейтинги."""
    async with AsyncSessionLocal() as session:
        ids = list((await session.scalars(select(Manga.id))).all())

    updated = 0
    for manga_id in ids:
        result = await recalculate_manga_rating(ctx, manga_id)
        if "rating" in result:
            updated += 1
    return {"total": len(ids), "updated": updated}


class WorkerSettings:
    functions = [recalculate_manga_rating, recalculate_all_ratings]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
