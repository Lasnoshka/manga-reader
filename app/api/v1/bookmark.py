from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ResourceAlreadyExistsError, ResourceNotFoundError
from app.core.logger import log_api_call
from app.db.models.bookmark import Bookmark
from app.db.models.manga import Manga
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

ALLOWED_FOLDERS = {"reading", "planned", "completed", "dropped", "favorite"}


class BookmarkCreateRequest(BaseModel):
    manga_id: int
    folder: str = Field(default="reading")


class BookmarkUpdateRequest(BaseModel):
    folder: str


class BookmarkResponse(BaseModel):
    id: int
    manga_id: int
    folder: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _validate_folder(folder: str) -> None:
    if folder not in ALLOWED_FOLDERS:
        from app.core.exceptions import BadRequestError

        raise BadRequestError(
            message=f"Unsupported folder '{folder}'",
            details={"allowed": sorted(ALLOWED_FOLDERS)},
        )


@router.post("/", response_model=BookmarkResponse, status_code=201)
@log_api_call
async def add_bookmark(
    payload: BookmarkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_folder(payload.folder)

    manga = await db.scalar(select(Manga.id).where(Manga.id == payload.manga_id))
    if manga is None:
        raise ResourceNotFoundError(resource="Manga", identifier=payload.manga_id)

    existing = await db.scalar(
        select(Bookmark).where(
            Bookmark.user_id == current_user.id, Bookmark.manga_id == payload.manga_id
        )
    )
    if existing is not None:
        raise ResourceAlreadyExistsError(resource="Bookmark", identifier=payload.manga_id)

    bookmark = Bookmark(
        user_id=current_user.id, manga_id=payload.manga_id, folder=payload.folder
    )
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


@router.get("/", response_model=List[BookmarkResponse])
@log_api_call
async def list_bookmarks(
    folder: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Bookmark).where(Bookmark.user_id == current_user.id)
    if folder is not None:
        _validate_folder(folder)
        query = query.where(Bookmark.folder == folder)
    query = query.order_by(Bookmark.created_at.desc())
    return list((await db.scalars(query)).all())


@router.patch("/{manga_id}", response_model=BookmarkResponse)
@log_api_call
async def update_bookmark(
    manga_id: int,
    payload: BookmarkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_folder(payload.folder)
    bookmark = await db.scalar(
        select(Bookmark).where(
            Bookmark.user_id == current_user.id, Bookmark.manga_id == manga_id
        )
    )
    if bookmark is None:
        raise ResourceNotFoundError(resource="Bookmark", identifier=manga_id)
    bookmark.folder = payload.folder
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


@router.delete("/{manga_id}")
@log_api_call
async def remove_bookmark(
    manga_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bookmark = await db.scalar(
        select(Bookmark).where(
            Bookmark.user_id == current_user.id, Bookmark.manga_id == manga_id
        )
    )
    if bookmark is None:
        raise ResourceNotFoundError(resource="Bookmark", identifier=manga_id)
    await db.delete(bookmark)
    await db.commit()
    return {"success": True}
