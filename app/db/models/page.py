from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Page(Base):
    __tablename__ = "page"
    __table_args__ = (UniqueConstraint("chapter_id", "page_number", name="uq_page_chapter_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapter.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)

    # Связь с главой
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="pages")

    def __repr__(self):
        return f"<Page(id={self.id}, chapter_id={self.chapter_id}, page_number={self.page_number})>"
