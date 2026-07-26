"""add download tracking to cv_requests

Revision ID: 002
Revises: 001_create_users
Create Date: 2026-02-02

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002_add_cv_download_tracking"
down_revision = "001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add downloaded_at column (nullable, defaults to NULL for existing records)
    op.add_column(
        "cv_requests",
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add download_count column (defaults to 0 for existing records)
    op.add_column(
        "cv_requests",
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("cv_requests", "download_count")
    op.drop_column("cv_requests", "downloaded_at")
