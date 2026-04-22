from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.client import delete_pattern
from app.cache.keys import chapter_pages_key
from app.core.exceptions import BadRequestError, ResourceAlreadyExistsError, ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.page import Page
from app.db.session_runtime import get_db

router = APIRouter(prefix="/page", tags=["pages"])


class PageCreateRequest(BaseModel):
    chapter_id: int
    page_number: int
    image_path: str
    width: Optional[int] = None
    height: Optional[int] = None


class PageUpdateRequest(BaseModel):
    page_number: Optional[int] = None
    image_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class PageResponse(BaseModel):
    id: int
    chapter_id: int
    page_number: int
    image_path: str
    width: Optional[int] = None
    height: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PagesBulkCreateRequest(BaseModel):
    pages: List[PageCreateRequest]


class PageListResponse(BaseModel):
    total: int
    items: List[PageResponse]
    page: int
    size: int
    pages: int


async def _get_chapter_or_404(db: AsyncSession, chapter_id: int) -> Chapter:
    chapter = await db.scalar(select(Chapter).where(Chapter.id == chapter_id))
    if chapter is None:
        raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)
    return chapter


async def _get_page_or_404(db: AsyncSession, page_id: int) -> Page:
    page = await db.scalar(select(Page).where(Page.id == page_id))
    if page is None:
        raise ResourceNotFoundError(resource="Page", identifier=page_id)
    return page


async def _ensure_unique_page_number(
    db: AsyncSession,
    chapter_id: int,
    page_number: int,
    exclude_id: Optional[int] = None,
) -> None:
    query = select(Page).where(Page.chapter_id == chapter_id, Page.page_number == page_number)
    if exclude_id is not None:
        query = query.where(Page.id != exclude_id)

    existing = await db.scalar(query)
    if existing is not None:
        raise ResourceAlreadyExistsError(resource="Page", identifier=f"{chapter_id}:{page_number}")


async def _invalidate_page_cache(chapter_id: int) -> None:
    await delete_pattern(chapter_pages_key(chapter_id))


@router.post("/", response_model=PageResponse, status_code=201)
@log_api_call
async def create_page(page_data: PageCreateRequest, db: AsyncSession = Depends(get_db)):
    chapter = await _get_chapter_or_404(db, page_data.chapter_id)
    await _ensure_unique_page_number(db, page_data.chapter_id, page_data.page_number)

    page = Page(**page_data.model_dump())
    db.add(page)
    chapter.pages_count += 1
    await db.commit()
    await db.refresh(page)
    await _invalidate_page_cache(chapter.id)
    return page


@router.post("/bulk", response_model=List[PageResponse], status_code=201)
@log_api_call
async def create_pages_bulk(data: PagesBulkCreateRequest, db: AsyncSession = Depends(get_db)):
    if not data.pages:
        raise BadRequestError(message="No pages provided")

    chapter_id = data.pages[0].chapter_id
    if any(item.chapter_id != chapter_id for item in data.pages):
        raise BadRequestError(message="All pages must belong to the same chapter")

    chapter = await _get_chapter_or_404(db, chapter_id)
    created_pages: List[Page] = []

    for page_data in data.pages:
        await _ensure_unique_page_number(db, chapter_id, page_data.page_number)
        page = Page(**page_data.model_dump())
        db.add(page)
        created_pages.append(page)

    chapter.pages_count += len(created_pages)
    await db.commit()
    for page in created_pages:
        await db.refresh(page)
    await _invalidate_page_cache(chapter.id)
    return created_pages


@router.get("/", response_model=PageListResponse)
@log_api_call
async def get_pages(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    chapter_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    count_query = select(func.count()).select_from(Page)
    data_query = select(Page)
    if chapter_id is not None:
        count_query = count_query.where(Page.chapter_id == chapter_id)
        data_query = data_query.where(Page.chapter_id == chapter_id)

    total = int((await db.execute(count_query)).scalar_one())
    pages = list(
        (
            await db.scalars(
                data_query.order_by(Page.chapter_id.asc(), Page.page_number.asc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
    )
    return {
        "total": total,
        "items": pages,
        "page": page,
        "size": size,
        "pages": ceil(total / size) if total else 0,
    }


@router.get("/{page_id}", response_model=PageResponse)
@log_api_call
async def get_page(page_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_page_or_404(db, page_id)


@router.put("/{page_id}", response_model=PageResponse)
@router.patch("/{page_id}", response_model=PageResponse)
@log_api_call
async def update_page(
    page_id: int,
    page_data: PageUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    page = await _get_page_or_404(db, page_id)
    update_data = page_data.model_dump(exclude_unset=True)

    if "page_number" in update_data:
        await _ensure_unique_page_number(db, page.chapter_id, update_data["page_number"], exclude_id=page_id)

    for field, value in update_data.items():
        setattr(page, field, value)

    await db.commit()
    await db.refresh(page)
    await _invalidate_page_cache(page.chapter_id)
    return page


@router.delete("/{page_id}")
@log_api_call
async def delete_page(page_id: int, db: AsyncSession = Depends(get_db)):
    page = await _get_page_or_404(db, page_id)
    chapter = await _get_chapter_or_404(db, page.chapter_id)
    chapter.pages_count = max(0, chapter.pages_count - 1)
    await db.delete(page)
    await db.commit()
    await _invalidate_page_cache(chapter.id)
    return {
        "success": True,
        "message": f"Page {page_id} deleted successfully",
    }
