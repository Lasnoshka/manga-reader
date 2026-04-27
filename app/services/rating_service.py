"""Aggregation helpers for user-attributed manga ratings.

Recalculates the cached `Manga.rating` (avg) and `Manga.rating_count` from
the `manga_ratings` table. Caller is responsible for committing.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.manga import Manga
from app.db.models.rating import MangaRating


async def recompute_manga_rating(session: AsyncSession, manga_id: int) -> dict:
    """Update cached avg/count on Manga in-place. Does not commit."""
    row = (
        await session.execute(
            select(
                func.avg(MangaRating.score),
                func.count(MangaRating.id),
            ).where(MangaRating.manga_id == manga_id)
        )
    ).one()
    avg_score, count = row
    avg_value = float(avg_score) if avg_score is not None else 0.0

    manga = await session.get(Manga, manga_id)
    if manga is None:
        return {"manga_id": manga_id, "average": 0.0, "count": 0, "found": False}

    manga.rating = round(avg_value, 2)
    manga.rating_count = int(count)
    return {
        "manga_id": manga_id,
        "average": manga.rating,
        "count": manga.rating_count,
        "found": True,
    }
