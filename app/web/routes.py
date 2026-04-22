from math import ceil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import Response

from app.core.exceptions import ResourceNotFoundError
from app.db.models.chapter import Chapter
from app.db.models.comment import Comment
from app.db.models.genre import Genre
from app.db.models.like import MangaLike
from app.db.models.manga import Manga
from app.db.models.page import Page
from app.db.session_runtime import get_db


web_router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


ALLOWED_SORT = {
    "newest": (Manga.created_at.desc(), "Сначала новые"),
    "oldest": (Manga.created_at.asc(), "Сначала старые"),
    "rating": (Manga.rating.desc(), "По рейтингу"),
    "title": (Manga.title.asc(), "По алфавиту"),
}


async def _all_genres(db: AsyncSession) -> list[Genre]:
    return list((await db.scalars(select(Genre).order_by(Genre.name.asc()))).all())


@web_router.get("/", response_class=HTMLResponse)
async def index_page(request: Request, db: AsyncSession = Depends(get_db)):
    popular = list(
        (
            await db.scalars(
                select(Manga)
                .options(selectinload(Manga.genres))
                .order_by(Manga.rating.desc(), Manga.created_at.desc())
                .limit(6)
            )
        ).all()
    )
    latest = list(
        (
            await db.scalars(
                select(Manga)
                .options(selectinload(Manga.genres))
                .order_by(Manga.created_at.desc())
                .limit(12)
            )
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"popular": popular, "latest": latest, "active_nav": "home"},
    )


@web_router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    page: int = Query(1, ge=1),
    sort: str = Query("newest"),
    genre: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if sort not in ALLOWED_SORT:
        sort = "newest"
    size = 24

    base_query = select(Manga).options(selectinload(Manga.genres))
    count_query = select(func.count(func.distinct(Manga.id))).select_from(Manga)

    if genre:
        base_query = base_query.join(Manga.genres)
        count_query = count_query.join(Manga.genres)
        base_query = base_query.where(func.lower(Genre.name) == genre.lower())
        count_query = count_query.where(func.lower(Genre.name) == genre.lower())

    if q:
        like_pattern = f"%{q.strip()}%"
        base_query = base_query.where(Manga.title.ilike(like_pattern) | Manga.author.ilike(like_pattern))
        count_query = count_query.where(Manga.title.ilike(like_pattern) | Manga.author.ilike(like_pattern))

    total = int((await db.execute(count_query)).scalar_one())
    ordering, _ = ALLOWED_SORT[sort]
    base_query = base_query.distinct().order_by(ordering).offset((page - 1) * size).limit(size)
    items = list((await db.scalars(base_query)).all())

    genres = await _all_genres(db)
    pages_total = max(1, ceil(total / size)) if total else 1

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "items": items,
            "genres": genres,
            "selected_genre": genre,
            "selected_sort": sort,
            "sort_options": [(k, v[1]) for k, v in ALLOWED_SORT.items()],
            "query": q or "",
            "page": page,
            "pages_total": pages_total,
            "total": total,
            "active_nav": "catalog",
        },
    )


@web_router.get("/manga/{manga_id}", response_class=HTMLResponse)
async def manga_page(manga_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    manga = await db.scalar(
        select(Manga).options(selectinload(Manga.genres)).where(Manga.id == manga_id)
    )
    if manga is None:
        raise ResourceNotFoundError(resource="Manga", identifier=manga_id)

    chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(Chapter.manga_id == manga_id)
                .order_by(Chapter.number.desc())
            )
        ).all()
    )
    likes_count = int(
        (
            await db.execute(select(func.count(MangaLike.id)).where(MangaLike.manga_id == manga_id))
        ).scalar_one()
    )
    comments_count = int(
        (
            await db.execute(select(func.count(Comment.id)).where(Comment.manga_id == manga_id))
        ).scalar_one()
    )

    return templates.TemplateResponse(
        request,
        "manga.html",
        {
            "manga": manga,
            "chapters": chapters,
            "likes_count": likes_count,
            "comments_count": comments_count,
            "active_nav": "catalog",
        },
    )


@web_router.get("/read/{chapter_id}", response_class=HTMLResponse)
async def reader_page(chapter_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    chapter = await db.scalar(select(Chapter).where(Chapter.id == chapter_id))
    if chapter is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)

    manga = await db.scalar(select(Manga).where(Manga.id == chapter.manga_id))

    pages = list(
        (
            await db.scalars(
                select(Page).where(Page.chapter_id == chapter_id).order_by(Page.page_number.asc())
            )
        ).all()
    )

    all_chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(Chapter.manga_id == chapter.manga_id)
                .order_by(Chapter.number.asc())
            )
        ).all()
    )
    ids_in_order = [ch.id for ch in all_chapters]
    try:
        idx = ids_in_order.index(chapter_id)
    except ValueError:
        idx = -1

    prev_id = ids_in_order[idx - 1] if idx > 0 else None
    next_id = ids_in_order[idx + 1] if 0 <= idx < len(ids_in_order) - 1 else None

    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "manga": manga,
            "chapter": chapter,
            "pages": pages,
            "prev_id": prev_id,
            "next_id": next_id,
            "all_chapters": all_chapters,
            "active_nav": None,
        },
    )


@web_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request, "auth/login.html", {"active_nav": None}
    )


@web_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request, "auth/register.html", {"active_nav": None}
    )


@web_router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(
        request, "profile.html", {"active_nav": "profile"}
    )


@web_router.get("/admin/manga", response_class=HTMLResponse)
async def admin_manga_page(request: Request, db: AsyncSession = Depends(get_db)):
    genres = await _all_genres(db)
    return templates.TemplateResponse(
        request,
        "admin/manga.html",
        {"genres": genres, "active_nav": "admin"},
    )


@web_router.get("/logout")
async def logout_page():
    return RedirectResponse(url="/", status_code=302)


@web_router.get("/reader")
async def legacy_reader():
    return RedirectResponse(url="/", status_code=302)


@web_router.get("/demo/page-image/{manga_slug}/{chapter_number}/{page_number}.svg")
async def demo_page_image(manga_slug: str, chapter_number: int, page_number: int):
    label = f"{manga_slug.replace('-', ' ').title()} / Ch. {chapter_number} / Page {page_number}"
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='960' height='1400'>
      <defs>
        <linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>
          <stop offset='0%' stop-color='#1f2330' />
          <stop offset='100%' stop-color='#11141d' />
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='url(#g)' />
      <rect x='64' y='64' width='832' height='1272' rx='32' fill='#1a1d27' stroke='#2a2f3d' stroke-width='2' />
      <text x='480' y='680' text-anchor='middle' fill='#ff7a45' font-size='42' font-family='Arial' font-weight='700'>
        {label}
      </text>
      <text x='480' y='740' text-anchor='middle' fill='#8a90a3' font-size='26' font-family='Arial'>
        Demo page placeholder
      </text>
    </svg>
    """.strip()
    return Response(svg, media_type="image/svg+xml")
