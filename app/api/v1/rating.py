from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.cache.client import delete_pattern
from app.cache.keys import manga_cache_pattern
from app.core.exceptions import ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.manga import Manga
from app.db.models.rating import MangaRating
from app.db.models.user import User
from app.db.session_runtime import get_db
from app.services.rating_service import recompute_manga_rating


router = APIRouter(prefix="/manga/{manga_id}/rating", tags=["ratings"])


class RatingUpsertRequest(BaseModel):
    score: int = Field(
        ge=1,
        le=10,
        description="Integer rating from 1 (worst) to 10 (best).",
        examples=[8],
    )


class RatingStatusResponse(BaseModel):
    manga_id: int = Field(examples=[42])
    average: float = Field(
        description="Mean of all submitted ratings, 0.0 if no votes yet.",
        examples=[8.4],
    )
    count: int = Field(description="Number of submitted ratings.", examples=[37])
    my_score: Optional[int] = Field(
        default=None,
        description="The current user's rating, or null if anonymous / not voted.",
        examples=[8],
    )


async def _ensure_manga_exists(db: AsyncSession, manga_id: int) -> None:
    exists = await db.scalar(select(Manga.id).where(Manga.id == manga_id))
    if exists is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)


async def _invalidate(manga_id: int) -> None:
    await delete_pattern(manga_cache_pattern())
    await delete_pattern("manga:popular:*")


@router.get("/", response_model=RatingStatusResponse)
@log_api_call
async def get_rating_status(
    manga_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    manga = await db.scalar(select(Manga).where(Manga.id == manga_id))
    if manga is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)

    my_score: Optional[int] = None
    if current_user is not None:
        my_score = await db.scalar(
            select(MangaRating.score).where(
                MangaRating.user_id == current_user.id,
                MangaRating.manga_id == manga_id,
            )
        )

    return RatingStatusResponse(
        manga_id=manga_id,
        average=manga.rating or 0.0,
        count=manga.rating_count or 0,
        my_score=my_score,
    )


@router.put("/", response_model=RatingStatusResponse)
@log_api_call
async def upsert_rating(
    manga_id: int,
    payload: RatingUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_manga_exists(db, manga_id)

    rating = await db.scalar(
        select(MangaRating).where(
            MangaRating.user_id == current_user.id,
            MangaRating.manga_id == manga_id,
        )
    )
    if rating is None:
        rating = MangaRating(
            user_id=current_user.id, manga_id=manga_id, score=payload.score
        )
        db.add(rating)
    else:
        rating.score = payload.score

    await db.flush()
    summary = await recompute_manga_rating(db, manga_id)
    await db.commit()
    await _invalidate(manga_id)

    return RatingStatusResponse(
        manga_id=manga_id,
        average=summary["average"],
        count=summary["count"],
        my_score=payload.score,
    )


@router.delete("/", response_model=RatingStatusResponse)
@log_api_call
async def remove_rating(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_manga_exists(db, manga_id)

    rating = await db.scalar(
        select(MangaRating).where(
            MangaRating.user_id == current_user.id,
            MangaRating.manga_id == manga_id,
        )
    )
    if rating is not None:
        await db.delete(rating)
        await db.flush()
        summary = await recompute_manga_rating(db, manga_id)
        await db.commit()
        await _invalidate(manga_id)
        return RatingStatusResponse(
            manga_id=manga_id,
            average=summary["average"],
            count=summary["count"],
            my_score=None,
        )

    manga = await db.scalar(select(Manga).where(Manga.id == manga_id))
    return RatingStatusResponse(
        manga_id=manga_id,
        average=manga.rating or 0.0,
        count=manga.rating_count or 0,
        my_score=None,
    )
