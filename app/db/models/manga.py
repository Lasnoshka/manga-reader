from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base
from app.db.models.genre import manga_genres


class Manga(Base):
    __tablename__ = "manga"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    cover_image: Mapped[Optional[str]] = mapped_column(String(500))
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter",
        back_populates="manga",
        cascade="all, delete-orphan",
    )

    genres: Mapped[List["Genre"]] = relationship(
        "Genre",
        secondary=manga_genres,
        back_populates="mangas",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Manga(id={self.id}, title='{self.title}')>"
