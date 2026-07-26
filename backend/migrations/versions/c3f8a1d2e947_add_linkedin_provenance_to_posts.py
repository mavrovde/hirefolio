"""Add LinkedIn provenance columns to posts

Revision ID: c3f8a1d2e947
Revises: d45b3e9ce716
Create Date: 2026-07-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a1d2e947"
down_revision: str | None = "d45b3e9ce716"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("source_urn", sa.String(), nullable=True))
    op.add_column(
        "posts", sa.Column("source_url", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "posts", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_post_source_urn_unique",
        "posts",
        ["source_urn"],
        unique=True,
        postgresql_where=sa.text("source_urn IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_post_source_urn_unique", table_name="posts")
    op.drop_column("posts", "posted_at")
    op.drop_column("posts", "source_url")
    op.drop_column("posts", "source_urn")
