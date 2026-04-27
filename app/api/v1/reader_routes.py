from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cache.client import get_json, set_json
from app.cache.keys import chapter_pages_key, search_results_key, search_suggest_key
from app.config import settings
from app.core.exceptions import ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.genre import Genre
from app.db.models.manga import Manga
from app.db.models.page import Page
from app.db.session_runtime import get_db
from app.services.fuzzy_search import fuzzy_rank

router = APIRouter(tags=["reader"])


class SearchGenreResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class SearchMangaResponse(BaseModel):
    id: int
    title: str
    description: str
    cover_image: Optional[str] = None
    author: Optional[str] = None
    rating: float
    genres: List[SearchGenreResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ChapterDetailResponse(BaseModel):
    id: int
    manga_id: int
    number: float
    title: Optional[str] = None
    volume: Optional[int] = None
    pages_count: int
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime
    manga_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PageResponse(BaseModel):
    id: int
    chapter_id: int
    page_number: int
    image_path: str
    width: Optional[int] = None
    height: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SearchSuggestion(BaseModel):
    id: int = Field(examples=[42])
    title: str = Field(examples=["Berserk"])
    author: Optional[str] = Field(default=None, examples=["Kentaro Miura"])
    cover_image: Optional[str] = Field(
        default=None, examples=["https://cdn.example.com/covers/berserk.jpg"]
    )

    model_config = ConfigDict(from_attributes=True)


SUGGEST_FUZZY_CANDIDATE_LIMIT = 200
SUGGEST_CACHE_TTL_SECONDS = 60


@router.get("/chapters/{chapter_id}", response_model=ChapterDetailResponse)
@log_api_call
async def get_chapter_detail(chapter_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter, Manga.title)
        .join(Manga, Chapter.manga_id == Manga.id)
        .where(Chapter.id == chapter_id)
    )
    row = result.first()
    if row is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)

    chapter, manga_title = row
    payload = ChapterDetailResponse.model_validate(chapter)
    payload.manga_title = manga_title
    return payload


@router.get("/chapters/{chapter_id}/pages", response_model=List[PageResponse])
@log_api_call
async def get_chapter_pages(chapter_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = chapter_pages_key(chapter_id)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    chapter = await db.scalar(select(Chapter.id).where(Chapter.id == chapter_id))
    if chapter is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)

    pages = list(
        (
            await db.scalars(
                select(Page).where(Page.chapter_id == chapter_id).order_by(Page.page_number.asc())
            )
        ).all()
    )
    payload = [PageResponse.model_validate(item).model_dump(mode="json") for item in pages]
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    return payload


@router.get("/search", response_model=List[SearchMangaResponse])
@log_api_call
async def search_manga(
    q: str = Query(..., min_length=1, description="Search by title, author, description, or genre"),
    genre: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query_text = q.strip()
    cache_key = search_results_key(query_text, genre, limit)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    statement = select(Manga).options(selectinload(Manga.genres)).outerjoin(Manga.genres).distinct()
    filters = [
        Manga.title.ilike(f"%{query_text}%"),
        Manga.author.ilike(f"%{query_text}%"),
        Manga.description.ilike(f"%{query_text}%"),
    ]
    if genre:
        statement = statement.where(Genre.name.ilike(genre))

    statement = (
        statement.where(or_(*filters, Genre.name.ilike(f"%{query_text}%")))
        .order_by(Manga.rating.desc(), Manga.created_at.desc())
        .limit(limit)
    )
    mangas = list((await db.scalars(statement)).unique().all())

    if len(mangas) < limit:
        seen_ids = {m.id for m in mangas}
        fuzzy_extras = await _fuzzy_expand_search(
            db, query_text, genre, limit=limit - len(mangas), seen_ids=seen_ids
        )
        mangas.extend(fuzzy_extras)

    payload = [SearchMangaResponse.model_validate(item).model_dump(mode="json") for item in mangas]
    await set_json(cache_key, payload, settings.CACHE_TTL_SECONDS)
    return payload


async def _fuzzy_expand_search(
    db: AsyncSession,
    query_text: str,
    genre: Optional[str],
    *,
    limit: int,
    seen_ids: set[int],
) -> List[Manga]:
    """Pull the most popular candidates and rank them by approximate match."""
    if limit <= 0:
        return []

    candidate_q = (
        select(Manga)
        .options(selectinload(Manga.genres))
        .order_by(Manga.rating.desc(), Manga.created_at.desc())
        .limit(SUGGEST_FUZZY_CANDIDATE_LIMIT)
    )
    if genre:
        candidate_q = candidate_q.join(Manga.genres).where(Genre.name.ilike(genre))

    candidates = list((await db.scalars(candidate_q)).unique().all())
    pool = [
        (m, [m.title, m.author or "", m.description or ""])
        for m in candidates
        if m.id not in seen_ids
    ]
    ranked = fuzzy_rank(query_text, pool, limit=limit)
    return [scored.item for scored in ranked]


@router.get("/search/suggest", response_model=List[SearchSuggestion])
@log_api_call
async def search_suggest(
    q: str = Query(..., min_length=1, max_length=120, description="Free-text query"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight typeahead endpoint for the topbar search.

    Combines an ilike prefix/substring lookup with fuzzy fallback so a
    one-letter typo (e.g. "berzerk") still surfaces "Berserk" without
    requiring a full /search round-trip.
    """
    query_text = q.strip()
    cache_key = search_suggest_key(query_text.lower(), limit)
    cached = await get_json(cache_key)
    if cached is not None:
        return cached

    pattern = f"%{query_text}%"
    fast_q = (
        select(Manga)
        .where(or_(Manga.title.ilike(pattern), Manga.author.ilike(pattern)))
        .order_by(Manga.rating.desc(), Manga.created_at.desc())
        .limit(limit * 2)
    )
    rows: List[Manga] = list((await db.scalars(fast_q)).all())
    seen_ids = {m.id for m in rows}

    if len(rows) < limit:
        rows.extend(
            await _fuzzy_expand_search(
                db, query_text, genre=None, limit=limit - len(rows), seen_ids=seen_ids
            )
        )

    rows = rows[:limit]
    payload = [
        SearchSuggestion.model_validate(item).model_dump(mode="json") for item in rows
    ]
    await set_json(cache_key, payload, SUGGEST_CACHE_TTL_SECONDS)
    return payload
