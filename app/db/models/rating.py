from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base


class MangaRating(Base):
    __tablename__ = "manga_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "manga_id", name="uq_rating_user_manga"),
        CheckConstraint("score BETWEEN 1 AND 10", name="ck_rating_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manga_id: Mapped[int] = mapped_column(
        ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="ratings")
