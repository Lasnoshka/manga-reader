from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    progress: Mapped[List["ReadingProgress"]] = relationship(
        "ReadingProgress", back_populates="user", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[List["Bookmark"]] = relationship(
        "Bookmark", back_populates="user", cascade="all, delete-orphan"
    )
    likes: Mapped[List["MangaLike"]] = relationship(
        "MangaLike", back_populates="user", cascade="all, delete-orphan"
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
