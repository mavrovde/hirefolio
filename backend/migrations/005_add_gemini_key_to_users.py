"""add gemini api key to users

Revision ID: 005
Revises: 004
Create Date: 2026-02-14

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_add_gemini_key_to_users"
down_revision = "004_add_subscribe_to_updates_to_cv_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("gemini_api_key", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "gemini_api_key")
