"""ARQ worker: фоновая обработка задач.

Запуск: `arq app.tasks.worker.WorkerSettings`
"""
from arq.connections import RedisSettings
from sqlalchemy import func, select

from app.cache.client import delete_pattern
from app.config import settings
from app.core.logger import logger
from app.db.models.like import MangaLike
from app.db.models.manga import Manga
from app.db.session_runtime import AsyncSessionLocal, init_engine


async def startup(ctx):
    init_engine()
    logger.info("ARQ worker started")


async def shutdown(ctx):
    logger.info("ARQ worker stopped")


async def recalculate_manga_rating(ctx, manga_id: int) -> dict:
    """Пересчитывает рейтинг манги: rating = min(10, likes * 0.5).

    Простая эвристика для демонстрации — реальный скоринг был бы сложнее.
    """
    async with AsyncSessionLocal() as session:
        manga = await session.get(Manga, manga_id)
        if manga is None:
            logger.warning(f"recalculate_manga_rating: manga {manga_id} not found")
            return {"manga_id": manga_id, "status": "not_found"}

        likes = int(
            (await session.execute(
                select(func.count(MangaLike.id)).where(MangaLike.manga_id == manga_id)
            )).scalar_one()
        )
        manga.rating = min(10.0, likes * 0.5)
        await session.commit()

    await delete_pattern(f"manga:detail:{manga_id}")
    await delete_pattern("manga:list:*")
    logger.info(f"recalculate_manga_rating: manga={manga_id} likes={likes} rating={manga.rating}")
    return {"manga_id": manga_id, "likes": likes, "rating": manga.rating}


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
