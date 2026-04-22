from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.datetime_utils import utcnow
from app.db.base import Base


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (UniqueConstraint("manga_id", "number", name="uq_chapter_manga_number"),)

    id = Column(Integer, primary_key=True, index=True)
    manga_id = Column(Integer, ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Float, nullable=False, index=True)
    title = Column(String, nullable=True)
    volume = Column(Integer, nullable=True)
    pages_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    manga = relationship("Manga", back_populates="chapters")
    pages = relationship("Page", back_populates="chapter", cascade="all, delete-orphan")
