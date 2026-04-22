"""bootstrap reader schema

Revision ID: 20260416_01
Revises:
Create Date: 2026-04-16 07:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_01"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _unique_constraint_exists(inspector: sa.Inspector, table_name: str, name: str) -> bool:
    return any(item["name"] == name for item in inspector.get_unique_constraints(table_name))


def _index_exists(inspector: sa.Inspector, table_name: str, name: str) -> bool:
    return any(item["name"] == name for item in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "manga"):
        op.create_table(
            "manga",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("author", sa.String(length=200), nullable=True),
            sa.Column("cover_image", sa.String(length=500), nullable=True),
            sa.Column("rating", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _index_exists(inspector, "manga", "ix_manga_id"):
        op.create_index("ix_manga_id", "manga", ["id"], unique=False)
    if not _index_exists(inspector, "manga", "ix_manga_title"):
        op.create_index("ix_manga_title", "manga", ["title"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "chapter"):
        op.create_table(
            "chapter",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False),
            sa.Column("number", sa.Float(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("volume", sa.Integer(), nullable=True),
            sa.Column("pages_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "chapter", "ix_chapter_id"):
        op.create_index("ix_chapter_id", "chapter", ["id"], unique=False)
    if not _index_exists(inspector, "chapter", "ix_chapter_manga_id"):
        op.create_index("ix_chapter_manga_id", "chapter", ["manga_id"], unique=False)
    if not _index_exists(inspector, "chapter", "ix_chapter_number"):
        op.create_index("ix_chapter_number", "chapter", ["number"], unique=False)
    if not _unique_constraint_exists(inspector, "chapter", "uq_chapter_manga_number"):
        op.create_unique_constraint("uq_chapter_manga_number", "chapter", ["manga_id", "number"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "page"):
        op.create_table(
            "page",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id", ondelete="CASCADE"), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("image_path", sa.String(length=500), nullable=False),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "page", "ix_page_id"):
        op.create_index("ix_page_id", "page", ["id"], unique=False)
    if not _index_exists(inspector, "page", "ix_page_chapter_id"):
        op.create_index("ix_page_chapter_id", "page", ["chapter_id"], unique=False)
    if not _index_exists(inspector, "page", "ix_page_page_number"):
        op.create_index("ix_page_page_number", "page", ["page_number"], unique=False)
    if not _unique_constraint_exists(inspector, "page", "uq_page_chapter_number"):
        op.create_unique_constraint("uq_page_chapter_number", "page", ["chapter_id", "page_number"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "genre"):
        op.create_table(
            "genre",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "genre", "ix_genre_id"):
        op.create_index("ix_genre_id", "genre", ["id"], unique=False)
    if not _index_exists(inspector, "genre", "ix_genre_name"):
        op.create_index("ix_genre_name", "genre", ["name"], unique=False)
    if not _unique_constraint_exists(inspector, "genre", "uq_genre_name"):
        op.create_unique_constraint("uq_genre_name", "genre", ["name"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "manga_genres"):
        op.create_table(
            "manga_genres",
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genre.id", ondelete="CASCADE"), primary_key=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "manga_genres"):
        op.drop_table("manga_genres")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "genre"):
        for index_name in ("ix_genre_id", "ix_genre_name"):
            if _index_exists(inspector, "genre", index_name):
                op.drop_index(index_name, table_name="genre")
        if _unique_constraint_exists(inspector, "genre", "uq_genre_name"):
            op.drop_constraint("uq_genre_name", "genre", type_="unique")
        op.drop_table("genre")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "page"):
        for index_name in ("ix_page_id", "ix_page_chapter_id", "ix_page_page_number"):
            if _index_exists(inspector, "page", index_name):
                op.drop_index(index_name, table_name="page")
        if _unique_constraint_exists(inspector, "page", "uq_page_chapter_number"):
            op.drop_constraint("uq_page_chapter_number", "page", type_="unique")
        op.drop_table("page")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "chapter"):
        for index_name in ("ix_chapter_id", "ix_chapter_manga_id", "ix_chapter_number"):
            if _index_exists(inspector, "chapter", index_name):
                op.drop_index(index_name, table_name="chapter")
        if _unique_constraint_exists(inspector, "chapter", "uq_chapter_manga_number"):
            op.drop_constraint("uq_chapter_manga_number", "chapter", type_="unique")
        op.drop_table("chapter")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "manga"):
        for index_name in ("ix_manga_id", "ix_manga_title"):
            if _index_exists(inspector, "manga", index_name):
                op.drop_index(index_name, table_name="manga")
        op.drop_table("manga")
