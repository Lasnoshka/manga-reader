"""user-attributed manga ratings

Revision ID: 20260428_03
Revises: 20260428_02
Create Date: 2026-04-28 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_03"
down_revision = "20260428_02"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "manga") and not _column_exists(
        inspector, "manga", "rating_count"
    ):
        op.add_column(
            "manga",
            sa.Column(
                "rating_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "manga_ratings"):
        op.create_table(
            "manga_ratings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "manga_id",
                sa.Integer(),
                sa.ForeignKey("manga.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("user_id", "manga_id", name="uq_rating_user_manga"),
            sa.CheckConstraint("score BETWEEN 1 AND 10", name="ck_rating_score_range"),
        )
        op.create_index("ix_manga_ratings_id", "manga_ratings", ["id"])
        op.create_index("ix_manga_ratings_user_id", "manga_ratings", ["user_id"])
        op.create_index("ix_manga_ratings_manga_id", "manga_ratings", ["manga_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "manga_ratings"):
        op.drop_table("manga_ratings")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "manga") and _column_exists(
        inspector, "manga", "rating_count"
    ):
        op.drop_column("manga", "rating_count")
