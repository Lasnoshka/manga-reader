from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "manga_id", name="uq_bookmark_user_manga"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manga_id: Mapped[int] = mapped_column(
        ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True
    )
    folder: Mapped[str] = mapped_column(String(32), nullable=False, default="reading")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="bookmarks")
