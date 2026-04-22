from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base


class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "manga_id", name="uq_progress_user_manga"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manga_id: Mapped[int] = mapped_column(
        ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapter.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="progress")

    def __repr__(self) -> str:
        return (
            f"<ReadingProgress(user_id={self.user_id}, manga_id={self.manga_id}, "
            f"chapter_id={self.chapter_id}, page={self.page_number})>"
        )
