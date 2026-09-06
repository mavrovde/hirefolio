"""Opportunity records which CV variant was sent, and when (#247 criterion 4).

Two nullable columns on `opportunities` — a SET NULL foreign key to
`cv_documents` plus the sent timestamp. SET NULL, not CASCADE: deleting a CV
version must not delete or corrupt the opportunity; the notes timeline keeps
the human-readable record (version + filename) even after the row goes.

Chained onto `interview0006` — two revisions sharing one down_revision give
Alembic two heads and `upgrade head` refuses to run.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cvvar0007"
down_revision: str | None = "interview0006"
branch_labels = None
depends_on = None

_COLUMNS = ("sent_cv_id", "sent_cv_at")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Self-adopt guard (lessons §23): the drift-guard job — and any pre-Alembic
    # host — materializes the CURRENT model with `create_all` before stamping,
    # so these columns can already exist. Compare COLUMN SETS, never
    # constraint/index names (the promote0005 lesson).
    existing = {c["name"] for c in inspector.get_columns("opportunities")}
    if "sent_cv_id" not in existing:
        op.add_column(
            "opportunities",
            sa.Column("sent_cv_id", sa.Uuid(), nullable=True),
        )
    # The FK guard is INDEPENDENT of the column guard (the promote0005 lesson,
    # #294 review): on a pre-Alembic DB create_all built column AND constraint
    # under its own auto-generated name, and a column could in principle exist
    # without the constraint. Compare by COLUMN SET, never by name.
    fks = {
        tuple(fk["constrained_columns"])
        for fk in inspector.get_foreign_keys("opportunities")
    }
    if ("sent_cv_id",) not in fks:
        op.create_foreign_key(
            "fk_opportunities_sent_cv_id",
            "opportunities",
            "cv_documents",
            ["sent_cv_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "sent_cv_at" not in existing:
        op.add_column(
            "opportunities",
            sa.Column("sent_cv_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # The FK's NAME depends on provenance: this migration names it, but a
    # pre-Alembic DB carries create_all's auto-generated name (measured:
    # `opportunities_sent_cv_id_fkey`, #294 review). Find it by column set.
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("opportunities"):
        if tuple(fk["constrained_columns"]) == ("sent_cv_id",):
            op.drop_constraint(fk["name"], "opportunities", type_="foreignkey")
    for name in reversed(_COLUMNS):
        op.drop_column("opportunities", name)
