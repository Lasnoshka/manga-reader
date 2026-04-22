"""add user, progress, bookmarks, likes, comments

Revision ID: 20260416_02
Revises: 20260416_01
Create Date: 2026-04-16 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_02"
down_revision = "20260416_01"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("avatar_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("username", name="uq_users_username"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_username", "users", ["username"])
        op.create_index("ix_users_email", "users", ["email"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "reading_progress"):
        op.create_table(
            "reading_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id", ondelete="CASCADE"), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "manga_id", name="uq_progress_user_manga"),
        )
        op.create_index("ix_reading_progress_id", "reading_progress", ["id"])
        op.create_index("ix_reading_progress_user_id", "reading_progress", ["user_id"])
        op.create_index("ix_reading_progress_manga_id", "reading_progress", ["manga_id"])
        op.create_index("ix_reading_progress_chapter_id", "reading_progress", ["chapter_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "bookmarks"):
        op.create_table(
            "bookmarks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False),
            sa.Column("folder", sa.String(length=32), nullable=False, server_default="reading"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "manga_id", name="uq_bookmark_user_manga"),
        )
        op.create_index("ix_bookmarks_id", "bookmarks", ["id"])
        op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])
        op.create_index("ix_bookmarks_manga_id", "bookmarks", ["manga_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "manga_likes"):
        op.create_table(
            "manga_likes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "manga_id", name="uq_like_user_manga"),
        )
        op.create_index("ix_manga_likes_id", "manga_likes", ["id"])
        op.create_index("ix_manga_likes_user_id", "manga_likes", ["user_id"])
        op.create_index("ix_manga_likes_manga_id", "manga_likes", ["manga_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "comments"):
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("manga_id", sa.Integer(), sa.ForeignKey("manga.id", ondelete="CASCADE"), nullable=True),
            sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id", ondelete="CASCADE"), nullable=True),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "(manga_id IS NOT NULL) OR (chapter_id IS NOT NULL)",
                name="ck_comment_target",
            ),
        )
        op.create_index("ix_comments_id", "comments", ["id"])
        op.create_index("ix_comments_user_id", "comments", ["user_id"])
        op.create_index("ix_comments_manga_id", "comments", ["manga_id"])
        op.create_index("ix_comments_chapter_id", "comments", ["chapter_id"])
        op.create_index("ix_comments_parent_id", "comments", ["parent_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in ("comments", "manga_likes", "bookmarks", "reading_progress", "users"):
        if _table_exists(inspector, table):
            op.drop_table(table)
        inspector = sa.inspect(bind)
