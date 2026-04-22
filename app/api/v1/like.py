from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.exceptions import ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.like import MangaLike
from app.db.models.manga import Manga
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/manga/{manga_id}/like", tags=["likes"])


class LikeStatusResponse(BaseModel):
    manga_id: int
    likes_count: int
    liked: bool


async def _likes_count(db: AsyncSession, manga_id: int) -> int:
    return int(
        (
            await db.execute(
                select(func.count(MangaLike.id)).where(MangaLike.manga_id == manga_id)
            )
        ).scalar_one()
    )


async def _ensure_manga_exists(db: AsyncSession, manga_id: int) -> None:
    exists = await db.scalar(select(Manga.id).where(Manga.id == manga_id))
    if exists is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)


@router.get("/", response_model=LikeStatusResponse)
@log_api_call
async def get_like_status(
    manga_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_manga_exists(db, manga_id)
    count = await _likes_count(db, manga_id)
    liked = False
    if current_user is not None:
        liked = (
            await db.scalar(
                select(MangaLike.id).where(
                    MangaLike.user_id == current_user.id, MangaLike.manga_id == manga_id
                )
            )
        ) is not None
    return LikeStatusResponse(manga_id=manga_id, likes_count=count, liked=liked)


@router.post("/", response_model=LikeStatusResponse, status_code=201)
@log_api_call
async def like_manga(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_manga_exists(db, manga_id)
    existing = await db.scalar(
        select(MangaLike).where(
            MangaLike.user_id == current_user.id, MangaLike.manga_id == manga_id
        )
    )
    if existing is None:
        db.add(MangaLike(user_id=current_user.id, manga_id=manga_id))
        await db.commit()
    count = await _likes_count(db, manga_id)
    return LikeStatusResponse(manga_id=manga_id, likes_count=count, liked=True)


@router.delete("/", response_model=LikeStatusResponse)
@log_api_call
async def unlike_manga(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_manga_exists(db, manga_id)
    existing = await db.scalar(
        select(MangaLike).where(
            MangaLike.user_id == current_user.id, MangaLike.manga_id == manga_id
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    count = await _likes_count(db, manga_id)
    return LikeStatusResponse(manga_id=manga_id, likes_count=count, liked=False)
