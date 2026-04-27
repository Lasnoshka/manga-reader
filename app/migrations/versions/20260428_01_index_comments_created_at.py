"""add index on comments.created_at

Revision ID: 20260428_01
Revises: 20260416_02
Create Date: 2026-04-28 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_01"
down_revision = "20260416_02"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_comments_created_at"


def _index_exists(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "comments" not in inspector.get_table_names():
        return
    if not _index_exists(inspector, "comments", INDEX_NAME):
        op.create_index(INDEX_NAME, "comments", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "comments" in inspector.get_table_names() and _index_exists(
        inspector, "comments", INDEX_NAME
    ):
        op.drop_index(INDEX_NAME, table_name="comments")
