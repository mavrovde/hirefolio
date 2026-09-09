"""Tailored application links (#250).

One new table, chained onto `trans0009` so the revision graph keeps exactly
one head (`alembic upgrade head` refuses to run with two).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "tailored0010"
down_revision: str | None = "trans0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Self-adopt guard (lessons §23): the pre-Alembic scenario materializes
    # every current model with create_all before stamping the baseline, so a
    # post-baseline CREATE must no-op when the table is already there.
    if sa.inspect(op.get_bind()).has_table("tailored_links"):
        return
    op.create_table(
        "tailored_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("cv_document_id", sa.Uuid(), nullable=True),
        sa.Column("headline_note", sa.Text(), nullable=True),
        sa.Column("highlighted_skills", postgresql.JSONB(), nullable=True),
        sa.Column("highlighted_projects", postgresql.JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visit_count", sa.Integer(), nullable=False),
        sa.Column("cv_download_count", sa.Integer(), nullable=False),
        sa.Column("last_visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cv_document_id"], ["cv_documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_tailored_links_opportunity",
        "tailored_links",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tailored_links_opportunity", table_name="tailored_links")
    op.drop_table("tailored_links")
