from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


manga_genres = Table(
    "manga_genres",
    Base.metadata,
    Column("manga_id", ForeignKey("manga.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genre.id", ondelete="CASCADE"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genre"
    __table_args__ = (UniqueConstraint("name", name="uq_genre_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    mangas: Mapped[list["Manga"]] = relationship(
        "Manga",
        secondary=manga_genres,
        back_populates="genres",
    )

    def __repr__(self) -> str:
        return f"<Genre(id={self.id}, name='{self.name}')>"
