"""unique promotion key on opportunities

Revision ID: promote0005
Revises: pipeline0004
Create Date: 2026-09-06 11:05:00.000000

Promote-from-inbox (#279) must be idempotent under CONCURRENCY, not just under
sequential calls. The application-level "look for an existing card" check races:
`get_db` yields a fresh session per request, so two clicks arriving together both
see "no card" and both insert — a review reproduced exactly that (two permanent
cards for one interaction, and the router ships no DELETE). Only a DB-level
UNIQUE closes it.

The key lives on `opportunities` rather than being derived from a note's
`interaction_id`, because notes are admin-writable: deriving it would let a
caller forge the key and make promote return an unrelated card.

Existing rows are backfilled from the promotion note each card already carries,
so cards created before this migration keep their idempotency. If a
pre-existing duplicate makes the backfill ambiguous, the OLDEST card wins and
the rest are left NULL (they stay reachable and editable — nothing is deleted;
the operator can merge them by hand).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "promote0005"
down_revision: str | None = "pipeline0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Self-adopt guard (lessons §23): the pre-Alembic scenario materializes the
    # CURRENT models via create_all before stamping, so the column may already
    # exist. Unlike a create_table this is a column-level check.
    columns = {c["name"] for c in inspector.get_columns("opportunities")}
    if "promoted_from_interaction_id" not in columns:
        op.add_column(
            "opportunities",
            sa.Column("promoted_from_interaction_id", sa.Uuid(), nullable=True),
        )

    # Backfill from the promotion note, oldest card wins on any pre-existing
    # duplicate so the UNIQUE below can be created without data loss.
    op.execute(
        sa.text(
            """
            UPDATE opportunities o
            SET promoted_from_interaction_id = w.interaction_id
            FROM (
                SELECT DISTINCT ON (n.interaction_id)
                       n.interaction_id, n.opportunity_id
                FROM opportunity_notes n
                JOIN opportunities oo ON oo.id = n.opportunity_id
                WHERE n.interaction_id IS NOT NULL
                ORDER BY n.interaction_id, oo.created_at ASC, oo.id ASC
            ) AS w
            WHERE o.id = w.opportunity_id
              AND o.promoted_from_interaction_id IS NULL
            """
        )
    )

    # Compare by COLUMN SET, never by name: on the pre-Alembic path `create_all`
    # emits an INLINE column UNIQUE that Postgres auto-names
    # `opportunities_promoted_from_interaction_id_key`, so a name check misses it
    # and adds a SECOND constraint (a review reproduced exactly that — two unique
    # constraints and two unique indexes on one column, invisible to `alembic
    # check`, which compares column sets rather than names).
    existing_cols = {
        tuple(c["column_names"])
        for c in inspector.get_unique_constraints("opportunities")
    }
    existing_cols |= {
        tuple(i["column_names"])
        for i in inspector.get_indexes("opportunities")
        if i.get("unique")
    }
    if ("promoted_from_interaction_id",) not in existing_cols:
        op.create_unique_constraint(
            "uq_opportunities_promoted_from_interaction_id",
            "opportunities",
            ["promoted_from_interaction_id"],
        )

    # The idempotency lookup and the notes timeline both filter on this column.
    indexes = {i["name"] for i in inspector.get_indexes("opportunity_notes")}
    if "ix_opportunity_notes_interaction_id" not in indexes:
        op.create_index(
            "ix_opportunity_notes_interaction_id",
            "opportunity_notes",
            ["interaction_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_opportunity_notes_interaction_id", table_name="opportunity_notes")
    op.drop_constraint(
        "uq_opportunities_promoted_from_interaction_id",
        "opportunities",
        type_="unique",
    )
    op.drop_column("opportunities", "promoted_from_interaction_id")
