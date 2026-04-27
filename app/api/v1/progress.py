from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.manga import Manga
from app.db.models.reading_progress import ReadingProgress
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/progress", tags=["progress"])


class ProgressUpsertRequest(BaseModel):
    manga_id: int = Field(description="Manga the user is reading.", examples=[42])
    chapter_id: int = Field(
        description="Current chapter; must belong to the given manga.",
        examples=[101],
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="1-indexed current page within the chapter.",
        examples=[7],
    )


class ProgressResponse(BaseModel):
    id: int = Field(examples=[5])
    manga_id: int = Field(examples=[42])
    chapter_id: int = Field(examples=[101])
    page_number: int = Field(description="1-indexed page.", examples=[7])
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.put("/", response_model=ProgressResponse)
@log_api_call
async def upsert_progress(
    payload: ProgressUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await db.scalar(
        select(Chapter).where(Chapter.id == payload.chapter_id, Chapter.manga_id == payload.manga_id)
    )
    if chapter is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=payload.chapter_id)

    progress = await db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.manga_id == payload.manga_id,
        )
    )
    if progress is None:
        progress = ReadingProgress(
            user_id=current_user.id,
            manga_id=payload.manga_id,
            chapter_id=payload.chapter_id,
            page_number=payload.page_number,
        )
        db.add(progress)
    else:
        progress.chapter_id = payload.chapter_id
        progress.page_number = payload.page_number

    await db.commit()
    await db.refresh(progress)
    return progress


@router.get("/", response_model=List[ProgressResponse])
@log_api_call
async def list_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = list(
        (
            await db.scalars(
                select(ReadingProgress)
                .where(ReadingProgress.user_id == current_user.id)
                .order_by(ReadingProgress.updated_at.desc())
            )
        ).all()
    )
    return rows


@router.get("/{manga_id}", response_model=ProgressResponse)
@log_api_call
async def get_progress(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    progress = await db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.manga_id == manga_id,
        )
    )
    if progress is None:
        raise ResourceNotFoundError(resource="ReadingProgress", identifier=manga_id)
    return progress


@router.delete("/{manga_id}")
@log_api_call
async def delete_progress(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    progress = await db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.manga_id == manga_id,
        )
    )
    if progress is None:
        raise ResourceNotFoundError(resource="ReadingProgress", identifier=manga_id)
    await db.delete(progress)
    await db.commit()
    return {"success": True}
