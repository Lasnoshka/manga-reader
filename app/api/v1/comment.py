from datetime import datetime
from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.exceptions import (
    AuthorizationError,
    BadRequestError,
    ResourceNotFoundError,
)
from app.core.logger import log_api_call
from app.db.models.chapter import Chapter
from app.db.models.comment import Comment
from app.db.models.manga import Manga
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/comments", tags=["comments"])


class CommentCreateRequest(BaseModel):
    manga_id: Optional[int] = Field(
        default=None,
        description="Target manga ID. Provide either manga_id, chapter_id, or parent_id.",
        examples=[42],
    )
    chapter_id: Optional[int] = Field(
        default=None,
        description="Target chapter ID; mutually optional with manga_id.",
        examples=[101],
    )
    parent_id: Optional[int] = Field(
        default=None,
        description=(
            "Parent comment ID for a reply. Replies inherit manga_id/chapter_id "
            "from the parent; replies-to-replies are not allowed."
        ),
        examples=[7],
    )
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="Comment body, 1–4000 characters.",
        examples=["Loved this chapter, the art was incredible."],
    )


class CommentUpdateRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="New comment body, 1–4000 characters.",
        examples=["Edited: also great pacing."],
    )


class CommentAuthor(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    id: int
    manga_id: Optional[int]
    chapter_id: Optional[int]
    parent_id: Optional[int]
    content: str
    created_at: datetime
    updated_at: datetime
    author: CommentAuthor

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    total: int
    items: List[CommentResponse]
    page: int
    size: int
    pages: int


def _serialize(comment: Comment) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        manga_id=comment.manga_id,
        chapter_id=comment.chapter_id,
        parent_id=comment.parent_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=CommentAuthor.model_validate(comment.user),
    )


@router.post("/", response_model=CommentResponse, status_code=201)
@log_api_call
async def create_comment(
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.manga_id is None and payload.chapter_id is None and payload.parent_id is None:
        raise BadRequestError("Comment requires manga_id, chapter_id, or parent_id")

    manga_id = payload.manga_id
    chapter_id = payload.chapter_id

    if payload.parent_id is not None:
        parent = await db.scalar(select(Comment).where(Comment.id == payload.parent_id))
        if parent is None:
            raise ResourceNotFoundError(resource="Comment", identifier=payload.parent_id)
        if parent.parent_id is not None:
            raise BadRequestError("Replies to replies are not allowed")
        manga_id = parent.manga_id
        chapter_id = parent.chapter_id

    if manga_id is not None:
        if (await db.scalar(select(Manga.id).where(Manga.id == manga_id))) is None:
            raise ResourceNotFoundError(resource="Manga", identifier=manga_id)
    if chapter_id is not None:
        if (await db.scalar(select(Chapter.id).where(Chapter.id == chapter_id))) is None:
            raise ResourceNotFoundError(resource="Chapter", identifier=chapter_id)

    comment = Comment(
        user_id=current_user.id,
        manga_id=manga_id,
        chapter_id=chapter_id,
        parent_id=payload.parent_id,
        content=payload.content.strip(),
    )
    db.add(comment)
    await db.commit()

    loaded = await db.scalar(
        select(Comment).options(selectinload(Comment.user)).where(Comment.id == comment.id)
    )
    return _serialize(loaded)


@router.get("/", response_model=CommentListResponse)
@log_api_call
async def list_comments(
    manga_id: Optional[int] = Query(None),
    chapter_id: Optional[int] = Query(None),
    parent_id: Optional[int] = Query(None, description="Filter replies; pass 0 for top-level only"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if manga_id is None and chapter_id is None and parent_id is None:
        raise BadRequestError("Provide at least one of manga_id, chapter_id, or parent_id")

    base_query = select(Comment).options(selectinload(Comment.user))
    count_query = select(func.count(Comment.id))

    if manga_id is not None:
        base_query = base_query.where(Comment.manga_id == manga_id)
        count_query = count_query.where(Comment.manga_id == manga_id)
    if chapter_id is not None:
        base_query = base_query.where(Comment.chapter_id == chapter_id)
        count_query = count_query.where(Comment.chapter_id == chapter_id)
    if parent_id is not None:
        if parent_id == 0:
            base_query = base_query.where(Comment.parent_id.is_(None))
            count_query = count_query.where(Comment.parent_id.is_(None))
        else:
            base_query = base_query.where(Comment.parent_id == parent_id)
            count_query = count_query.where(Comment.parent_id == parent_id)

    total = int((await db.execute(count_query)).scalar_one())
    rows = list(
        (
            await db.scalars(
                base_query.order_by(Comment.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
    )
    return CommentListResponse(
        total=total,
        items=[_serialize(c) for c in rows],
        page=page,
        size=size,
        pages=ceil(total / size) if total else 0,
    )


@router.patch("/{comment_id}", response_model=CommentResponse)
@log_api_call
async def update_comment(
    comment_id: int,
    payload: CommentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await db.scalar(
        select(Comment).options(selectinload(Comment.user)).where(Comment.id == comment_id)
    )
    if comment is None:
        raise ResourceNotFoundError(resource="Comment", identifier=comment_id)
    if comment.user_id != current_user.id and current_user.role != "admin":
        raise AuthorizationError("You can edit only your own comments")

    comment.content = payload.content.strip()
    await db.commit()
    await db.refresh(comment)
    return _serialize(comment)


@router.delete("/{comment_id}")
@log_api_call
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await db.scalar(select(Comment).where(Comment.id == comment_id))
    if comment is None:
        raise ResourceNotFoundError(resource="Comment", identifier=comment_id)
    if comment.user_id != current_user.id and current_user.role != "admin":
        raise AuthorizationError("You can delete only your own comments")

    await db.delete(comment)
    await db.commit()
    return {"success": True}
