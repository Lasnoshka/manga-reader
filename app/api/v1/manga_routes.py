from datetime import datetime
from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin
from app.cache.client import delete_pattern, get_json, get_sorted_set_desc, increment_sorted_set, set_json
from app.cache.keys import (
    genres_list_key,
    manga_chapters_key,
    manga_cache_pattern,
    manga_detail_key,
    manga_list_key,
    manga_popular_key,
    manga_views_key,
)
from app.config import settings
from app.core.exceptions import BadRequestError, ResourceAlreadyExistsError, ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.genre import Genre
from app.db.models.manga import Manga
from app.db.session_runtime import get_db

router = APIRouter(prefix="/manga", tags=["manga"])

ALLOWED_SORT_FIELDS = {"id", "title", "author", "rating", "created_at", "updated_at"}


class MangaCreateRequest(BaseModel):
    title: str = Field(
        description="Display title, must be unique (case-insensitive).",
        examples=["Berserk"],
    )
    description: str = Field(
        description="Long-form synopsis, plain text.",
        examples=["A wandering swordsman seeks revenge against his former friend."],
    )
    cover_image: Optional[str] = Field(
        default=None,
        description="Absolute URL to the cover image.",
        examples=["https://cdn.example.com/covers/berserk.jpg"],
    )
    author: Optional[str] = Field(
        default=None,
        description="Author name; free-form, optional.",
        examples=["Kentaro Miura"],
    )
    genres: List[str] = Field(
        default_factory=list,
        description="Genre names. Unknown ones are created on the fly.",
        examples=[["Action", "Dark Fantasy"]],
    )


class MangaUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, examples=["Berserk: Black Swordsman Edition"])
    description: Optional[str] = None
    cover_image: Optional[str] = None
    author: Optional[str] = None
    genres: Optional[List[str]] = Field(
        default=None,
        description="Replaces the full genre set; pass [] to clear.",
    )


class GenreResponse(BaseModel):
    id: int = Field(examples=[1])
    name: str = Field(examples=["Action"])

    model_config = ConfigDict(from_attributes=True)


class MangaResponse(BaseModel):
    id: int = Field(examples=[42])
    title: str = Field(examples=["Berserk"])
    description: str
    cover_image: Optional[str] = None
    author: Optional[str] = Field(default=None, examples=["Kentaro Miura"])
    rating: float = Field(
        description="Average user rating, 0.0–10.0; 0.0 when no votes yet.",
        examples=[8.4],
    )
    rating_count: int = Field(
        default=0,
        description="Number of users who have rated this manga.",
        examples=[37],
    )
    genres: List[GenreResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MangaListResponse(BaseModel):
    total: int = Field(description="Total matching items across all pages.", examples=[123])
    items: List[MangaResponse]
    page: int = Field(description="1-indexed page number.", examples=[1])
    size: int = Field(description="Items per page (1–100).", examples=[20])
    pages: int = Field(description="Total page count.", examples=[7])


class PopularMangaResponse(MangaResponse):
    views: int = Field(
        description="Total view count from the popularity ranking.",
        examples=[15234],
    )


class MangaChapterResponse(BaseModel):
    id: int = Field(examples=[101])
    manga_id: int = Field(examples=[42])
    number: float = Field(
        description="Chapter number; floats allow .5 / extra chapters.",
        examples=[12.5],
    )
    title: Optional[str] = Field(default=None, examples=["The Black Swordsman"])
    volume: Optional[int] = Field(default=None, examples=[3])
    pages_count: int = Field(examples=[24])
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


async def _get_manga_or_404(db: AsyncSession, manga_id: int) -> Manga:
    manga = await db.scalar(
        select(Manga).options(selectinload(Manga.genres)).where(Manga.id == manga_id)
    )
    if manga is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)
    return manga


async def _ensure_unique_title(db: AsyncSession, title: str, exclude_id: Optional[int] = None) -> None:
    query = select(Manga).where(func.lower(Manga.title) == title.lower())
    if exclude_id is not None:
        query = query.where(Manga.id != exclude_id)

    existing = await db.scalar(query)
    if existing is not None:
        raise ResourceAlreadyExistsError(resource="Manga", identifier=title)


async def _invalidate_manga_cache() -> None:
    await delete_pattern(manga_cache_pattern())
    await delete_pattern("search:*")
    await delete_pattern("genres:*")


async def _resolve_genres(db: AsyncSession, genre_names: List[str]) -> List[Genre]:
    normalized = []
    seen = set()
    for name in genre_names:
        clean_name = name.strip()
        if not clean_name:
            continue
        key = clean_name.lower()
        if key not in seen:
            normalized.append(clean_name)
            seen.add(key)

    if not normalized:
        return []

    existing = list(
        (
            await db.scalars(
                select(Genre).where(func.lower(Genre.name).in_([name.lower() for name in normalized]))
            )
        ).all()
    )
    by_name = {genre.name.lower(): genre for genre in existing}

    for name in normalized:
        key = name.lower()
        if key not in by_name:
            genre = Genre(name=name)
            db.add(genre)
            existing.append(genre)
            by_name[key] = genre

    return [by_name[name.lower()] for name in normalized]


def _serialize_manga_list(manga_items: List[Manga], total: int, page: int, size: int) -> dict:
    items = [MangaResponse.model_validate(item).model_dump(mode="json") for item in manga_items]
    return {
        "total": total,
        "items": items,
        "page": page,
        "size": size,
        "pages": ceil(total / size) if total else 0,
    }


@router.post("/", response_model=MangaResponse, status_code=201, dependencies=[Depends(require_admin)])
@log_api_call
async def create_manga(manga_data: MangaCreateRequest, db: AsyncSession = Depends(get_db)):
    await _ensure_unique_title(db, manga_data.title)

    payload = manga_data.model_dump()
    genres = await _resolve_genres(db, payload.pop("genres", []))
    new_manga = Manga(**payload)
    new_manga.genres = genres
    db.add(new_manga)
    await db.commit()
    await db.refresh(new_manga)
    await _invalidate_manga_cache()
    return new_manga


@router.get("/popular", response_model=List[PopularMangaResponse])
@log_api_call
async def get_popular_manga(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    cache_key = manga_popular_key(limit)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    ranked = await get_sorted_set_desc(manga_views_key(), 0, limit - 1, with_scores=True)
    if not ranked:
        fallback_query = (
            select(Manga)
            .options(selectinload(Manga.genres))
            .order_by(Manga.rating.desc(), Manga.created_at.desc())
            .limit(limit)
        )
        manga_items = list((await db.scalars(fallback_query)).all())
        payload = [
            PopularMangaResponse(**MangaResponse.model_validate(item).model_dump(), views=0).model_dump(mode="json")
            for item in manga_items
        ]
        await set_json(cache_key, payload, settings.POPULAR_TTL_SECONDS)
        return payload

    manga_ids = [int(item[0]) for item in ranked]
    score_map = {int(item[0]): int(item[1]) for item in ranked}
    manga_items = list(
        (
            await db.scalars(select(Manga).options(selectinload(Manga.genres)).where(Manga.id.in_(manga_ids)))
        ).all()
    )
    by_id = {item.id: item for item in manga_items}
    payload = [
        PopularMangaResponse(
            **MangaResponse.model_validate(by_id[manga_id]).model_dump(),
            views=score_map[manga_id],
        ).model_dump(mode="json")
        for manga_id in manga_ids
        if manga_id in by_id
    ]
    await set_json(cache_key, payload, settings.POPULAR_TTL_SECONDS)
    return payload


@router.get("/", response_model=MangaListResponse)
@log_api_call
async def get_all_manga(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_desc: bool = Query(True),
    title_contains: Optional[str] = Query(None),
    author_contains: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise BadRequestError(
            message=f"Unsupported sort field '{sort_by}'",
            details={"allowed_fields": sorted(ALLOWED_SORT_FIELDS)},
        )

    cache_key = manga_list_key(page, size, sort_by, sort_desc, title_contains, author_contains, genre)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    filters = []
    data_query = select(Manga).options(selectinload(Manga.genres))
    count_query = select(func.count(func.distinct(Manga.id))).select_from(Manga)

    if title_contains:
        filters.append(Manga.title.ilike(f"%{title_contains}%"))
    if author_contains:
        filters.append(Manga.author.ilike(f"%{author_contains}%"))
    if genre:
        data_query = data_query.join(Manga.genres)
        count_query = count_query.join(Manga.genres)
        filters.append(func.lower(Genre.name) == genre.lower())

    for filter_expr in filters:
        count_query = count_query.where(filter_expr)
        data_query = data_query.where(filter_expr)

    total = int((await db.execute(count_query)).scalar_one())
    sort_column = getattr(Manga, sort_by)
    ordering = sort_column.desc() if sort_desc else sort_column.asc()
    data_query = data_query.distinct().order_by(ordering).offset((page - 1) * size).limit(size)
    manga_items = list((await db.scalars(data_query)).all())

    payload = _serialize_manga_list(manga_items, total, page, size)
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    return payload


@router.get("/genres", response_model=List[GenreResponse])
@log_api_call
async def get_genres(db: AsyncSession = Depends(get_db)):
    cache_key = genres_list_key()
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    genres = list((await db.scalars(select(Genre).order_by(Genre.name.asc()))).all())
    payload = [GenreResponse.model_validate(item).model_dump(mode="json") for item in genres]
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    return payload


@router.get("/{manga_id}", response_model=MangaResponse)
@log_api_call
async def get_manga(manga_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = manga_detail_key(manga_id)
    cached = await get_json(cache_key)
    if cached is not None:
        await increment_sorted_set(manga_views_key(), str(manga_id))
        return cached

    manga = await _get_manga_or_404(db, manga_id)
    payload = MangaResponse.model_validate(manga).model_dump(mode="json")
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    await increment_sorted_set(manga_views_key(), str(manga_id))
    await delete_pattern("manga:popular:*")
    return payload


@router.get("/{manga_id}/chapters", response_model=List[MangaChapterResponse])
@log_api_call
async def get_manga_chapters(manga_id: int, db: AsyncSession = Depends(get_db)):
    await _get_manga_or_404(db, manga_id)

    cache_key = manga_chapters_key(manga_id)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    chapters = list(
        (
            await db.scalars(
                select(Chapter).where(Chapter.manga_id == manga_id).order_by(Chapter.number.asc(), Chapter.id.asc())
            )
        ).all()
    )
    payload = [MangaChapterResponse.model_validate(item).model_dump(mode="json") for item in chapters]
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    return payload


@router.put("/{manga_id}", response_model=MangaResponse, dependencies=[Depends(require_admin)])
@router.patch("/{manga_id}", response_model=MangaResponse, dependencies=[Depends(require_admin)])
@log_api_call
async def update_manga(
    manga_id: int,
    manga_data: MangaUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    manga = await _get_manga_or_404(db, manga_id)
    update_data = manga_data.model_dump(exclude_unset=True)

    if "title" in update_data:
        await _ensure_unique_title(db, update_data["title"], exclude_id=manga_id)

    genres_payload = update_data.pop("genres", None)
    for field, value in update_data.items():
        setattr(manga, field, value)
    if genres_payload is not None:
        manga.genres = await _resolve_genres(db, genres_payload)

    await db.commit()
    await db.refresh(manga)
    await _invalidate_manga_cache()
    return manga


@router.post("/{manga_id}/recalc-rating", status_code=202, dependencies=[Depends(require_admin)])
@log_api_call
async def enqueue_recalc_rating(manga_id: int, db: AsyncSession = Depends(get_db)):
    from app.tasks.queue import get_queue

    await _get_manga_or_404(db, manga_id)
    queue = await get_queue()
    if queue is None:
        raise BadRequestError("Task queue unavailable (Redis down)")
    job = await queue.enqueue_job("recalculate_manga_rating", manga_id)
    return {"job_id": job.job_id if job else None, "manga_id": manga_id, "status": "queued"}


@router.delete("/{manga_id}", dependencies=[Depends(require_admin)])
@log_api_call
async def delete_manga(manga_id: int, db: AsyncSession = Depends(get_db)):
    manga = await _get_manga_or_404(db, manga_id)
    title = manga.title
    await db.delete(manga)
    await db.commit()
    await _invalidate_manga_cache()
    return {
        "success": True,
        "message": f"Manga '{title}' (ID: {manga_id}) deleted successfully",
    }
