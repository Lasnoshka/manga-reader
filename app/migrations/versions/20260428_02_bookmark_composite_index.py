"""composite index on bookmarks(user_id, created_at)

Revision ID: 20260428_02
Revises: 20260428_01
Create Date: 2026-04-28 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_02"
down_revision = "20260428_01"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_bookmarks_user_created"


def _index_exists(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "bookmarks" not in inspector.get_table_names():
        return
    if not _index_exists(inspector, "bookmarks", INDEX_NAME):
        op.create_index(INDEX_NAME, "bookmarks", ["user_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "bookmarks" in inspector.get_table_names() and _index_exists(
        inspector, "bookmarks", INDEX_NAME
    ):
        op.drop_index(INDEX_NAME, table_name="bookmarks")
