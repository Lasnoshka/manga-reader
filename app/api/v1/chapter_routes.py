from datetime import datetime
from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.client import delete_pattern
from app.cache.keys import manga_chapters_key
from app.core.exceptions import BadRequestError, ResourceAlreadyExistsError, ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.manga import Manga
from app.db.session_runtime import get_db

router = APIRouter(prefix="/chapter", tags=["chapters"])

ALLOWED_SORT_FIELDS = {"id", "number", "volume", "pages_count", "uploaded_at", "created_at", "updated_at"}


class ChapterCreateRequest(BaseModel):
    manga_id: int
    number: float
    title: Optional[str] = None
    volume: Optional[int] = None


class ChapterUpdateRequest(BaseModel):
    number: Optional[float] = None
    title: Optional[str] = None
    volume: Optional[int] = None


class ChapterResponse(BaseModel):
    id: int
    manga_id: int
    number: float
    title: Optional[str] = None
    volume: Optional[int] = None
    pages_count: int
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChapterDetailResponse(ChapterResponse):
    manga_title: Optional[str] = None


class ChapterListResponse(BaseModel):
    total: int
    items: List[ChapterResponse]
    page: int
    size: int
    pages: int


class ChapterBulkCreateRequest(BaseModel):
    chapters: List[ChapterCreateRequest]


class ChapterBulkResponse(BaseModel):
    success: bool
    created: int = 0
    updated: int = 0
    deleted: int = 0
    details: Optional[List[str]] = None


async def _get_manga_or_404(db: AsyncSession, manga_id: int) -> Manga:
    manga = await db.scalar(select(Manga).where(Manga.id == manga_id))
    if manga is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)
    return manga


async def _get_chapter_or_404(db: AsyncSession, chapter_id: int) -> Chapter:
    chapter = await db.scalar(select(Chapter).where(Chapter.id == chapter_id))
    if chapter is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)
    return chapter


async def _ensure_unique_chapter_number(
    db: AsyncSession,
    manga_id: int,
    number: float,
    exclude_id: Optional[int] = None,
) -> None:
    query = select(Chapter).where(Chapter.manga_id == manga_id, Chapter.number == number)
    if exclude_id is not None:
        query = query.where(Chapter.id != exclude_id)

    existing = await db.scalar(query)
    if existing is not None:
        raise ResourceAlreadyExistsError(resource="Chapter", identifier=f"{manga_id}:{number}")


async def _invalidate_chapter_cache(manga_id: int) -> None:
    await delete_pattern(manga_chapters_key(manga_id))


@router.post("/", response_model=ChapterResponse, status_code=201)
@log_api_call
async def create_chapter(chapter_data: ChapterCreateRequest, db: AsyncSession = Depends(get_db)):
    await _get_manga_or_404(db, chapter_data.manga_id)
    await _ensure_unique_chapter_number(db, chapter_data.manga_id, chapter_data.number)

    chapter = Chapter(**chapter_data.model_dump())
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    await _invalidate_chapter_cache(chapter.manga_id)
    return chapter


@router.post("/bulk", response_model=ChapterBulkResponse, status_code=201)
@log_api_call
async def create_chapter_bulk(data: ChapterBulkCreateRequest, db: AsyncSession = Depends(get_db)):
    if not data.chapters:
        raise BadRequestError(message="No chapter data provided")

    created = 0
    errors: List[str] = []
    existing_manga_ids = set(
        (await db.scalars(select(Manga.id).where(Manga.id.in_({item.manga_id for item in data.chapters})))).all()
    )

    for chapter_data in data.chapters:
        if chapter_data.manga_id not in existing_manga_ids:
            errors.append(f"Manga {chapter_data.manga_id} not found for chapter {chapter_data.number}")
            continue

        try:
            await _ensure_unique_chapter_number(db, chapter_data.manga_id, chapter_data.number)
        except ResourceAlreadyExistsError:
            errors.append(f"Chapter {chapter_data.number} already exists for manga {chapter_data.manga_id}")
            continue

        db.add(Chapter(**chapter_data.model_dump()))
        created += 1

    await db.commit()
    for manga_id in existing_manga_ids:
        await _invalidate_chapter_cache(manga_id)
    return ChapterBulkResponse(success=True, created=created, details=errors or None)


@router.get("/", response_model=ChapterListResponse)
@log_api_call
async def get_all_chapters(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    manga_id: Optional[int] = Query(None),
    sort_by: str = Query("number"),
    sort_desc: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise BadRequestError(
            message=f"Unsupported sort field '{sort_by}'",
            details={"allowed_fields": sorted(ALLOWED_SORT_FIELDS)},
        )

    count_query = select(func.count()).select_from(Chapter)
    data_query = select(Chapter)
    if manga_id is not None:
        count_query = count_query.where(Chapter.manga_id == manga_id)
        data_query = data_query.where(Chapter.manga_id == manga_id)

    total = int((await db.execute(count_query)).scalar_one())
    sort_column = getattr(Chapter, sort_by)
    ordering = sort_column.desc() if sort_desc else sort_column.asc()
    chapters = list(
        (
            await db.scalars(
                data_query.order_by(ordering).offset((page - 1) * size).limit(size)
            )
        ).all()
    )

    return {
        "total": total,
        "items": chapters,
        "page": page,
        "size": size,
        "pages": ceil(total / size) if total else 0,
    }


@router.get("/{chapter_id}", response_model=ChapterDetailResponse)
@log_api_call
async def get_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter, Manga.title).join(Manga, Chapter.manga_id == Manga.id).where(Chapter.id == chapter_id)
    )
    row = result.first()
    if row is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)

    chapter, manga_title = row
    payload = ChapterDetailResponse.model_validate(chapter)
    payload.manga_title = manga_title
    return payload


@router.put("/{chapter_id}", response_model=ChapterResponse)
@router.patch("/{chapter_id}", response_model=ChapterResponse)
@log_api_call
async def update_chapter(
    chapter_id: int,
    chapter_data: ChapterUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    chapter = await _get_chapter_or_404(db, chapter_id)
    update_data = chapter_data.model_dump(exclude_unset=True)

    if "number" in update_data:
        await _ensure_unique_chapter_number(db, chapter.manga_id, update_data["number"], exclude_id=chapter_id)

    for field, value in update_data.items():
        setattr(chapter, field, value)

    await db.commit()
    await db.refresh(chapter)
    await _invalidate_chapter_cache(chapter.manga_id)
    return chapter


@router.delete("/{chapter_id}")
@log_api_call
async def delete_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    chapter = await _get_chapter_or_404(db, chapter_id)
    number = chapter.number
    manga_id = chapter.manga_id
    await db.delete(chapter)
    await db.commit()
    await _invalidate_chapter_cache(manga_id)
    return {
        "success": True,
        "message": f"Chapter {number} (ID: {chapter_id}) deleted successfully",
    }
