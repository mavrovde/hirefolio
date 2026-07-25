"""Create profile_versions table (versioned, per-language profile snapshots)

Revision ID: a1b2c3d4e5f6
Revises: c3f8a1d2e947
Create Date: 2026-07-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c3f8a1d2e947"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.UniqueConstraint(
            "version", "language", name="uq_profile_version_language"
        ),
    )


def downgrade() -> None:
    op.drop_table("profile_versions")
