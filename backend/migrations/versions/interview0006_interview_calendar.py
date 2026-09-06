"""interview calendar

Revision ID: interview0006
Revises: promote0005
Create Date: 2026-09-06 14:40:00.000000

Job-search pipeline phase 2 (#247 / #70): the ``interviews`` table — the
concrete rounds behind an opportunity's ``interviewing`` stage, plus the two
indexes the product reads through (per-opportunity listing and the dashboard's
"next N days" range scan).

Chained onto `promote0005`, not `pipeline0004`: two revisions sharing one
`down_revision` give Alembic two heads and `upgrade head` refuses to run —
which is exactly what the drift-guard job caught on this PR the moment
`promote0005` merged to main while this branch still pointed at `pipeline0004`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "interview0006"
down_revision: str | None = "promote0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("ix_interviews_opportunity", ("opportunity_id",)),
    ("ix_interviews_scheduled_at", ("scheduled_at",)),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Self-adopt guard (lessons §23): the drift-guard job — and any pre-Alembic
    # host — materializes every CURRENT model with `create_all` before stamping
    # the baseline, so this table can already exist when the migration runs.
    if not inspector.has_table("interviews"):
        op.create_table(
            "interviews",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("opportunity_id", sa.Uuid(), nullable=False),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=30), nullable=False),
            sa.Column("location_or_link", sa.String(length=1000), nullable=True),
            sa.Column("interviewer", sa.String(length=200), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("outcome", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        for name, columns in _INDEXES:
            op.create_index(name, "interviews", list(columns), unique=False)
        return

    # Adopting a table `create_all` already built: add only what is missing, and
    # compare COLUMN SETS, never index/constraint NAMES. A name-based check is
    # what made `promote0005` add a SECOND unique constraint on the pre-Alembic
    # path (create_all's auto-generated name differs from the migration's), and
    # `alembic check` cannot see the duplicate because it compares column sets.
    existing = {tuple(i["column_names"]) for i in inspector.get_indexes("interviews")}
    for name, columns in _INDEXES:
        if columns not in existing:
            op.create_index(name, "interviews", list(columns), unique=False)


def downgrade() -> None:
    for name, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name="interviews")
    op.drop_table("interviews")
