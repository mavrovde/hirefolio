"""Engagement events table (#249).

Chained onto `tailored0010` (#250), NOT onto `trans0009` — this revision and
that one were authored in parallel off the same parent, and two revisions
sharing one `down_revision` give Alembic two heads: `upgrade head` then fails
with "Multiple head revisions are present". `docker-entrypoint.sh` runs exactly
that on every container start, so the fork is a boot failure, not a
housekeeping detail. Whichever of two parallel migrations merges second
re-chains behind the first; the revision id itself never changes, because a
deployed database may already have it stamped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "engage0010"
down_revision: str | None = "tailored0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Self-adopt guard (lessons §23): a pre-Alembic DB is materialized by
    # ``Base.metadata.create_all``, which already builds this table and its
    # indexes before baseline0001 is stamped.
    if sa.inspect(op.get_bind()).has_table("engagement_events"):
        return
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_engagement_events_created_at",
        "engagement_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_engagement_events_kind", "engagement_events", ["kind"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_engagement_events_kind", table_name="engagement_events")
    op.drop_index("ix_engagement_events_created_at", table_name="engagement_events")
    op.drop_table("engagement_events")
