"""Runtime site settings table — first key: availability (#271).

Chained onto `cvvar0007` — two revisions sharing one down_revision give
Alembic two heads and `upgrade head` refuses to run.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "avail0008"
down_revision: str | None = "cvvar0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Self-adopt guard (lessons §23): create_all may have built this already.
    if inspector.has_table("site_settings"):
        return
    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
