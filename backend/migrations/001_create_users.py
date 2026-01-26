"""create users table

Revision ID: 001
Revises:
Create Date: 2026-01-24

"""

from alembic import op
import sqlalchemy as sa
from app.services.auth import get_password_hash


# revision identifiers, used by Alembic.
revision = "001_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # Create indexes
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # Insert default admin user
    # Password: admin
    hashed_password = get_password_hash("admin")
    op.execute(
        f"""
        INSERT INTO users (username, email, hashed_password, is_admin, is_active)
        VALUES ('admin', 'admin@mavrov.de', '{hashed_password}', true, true)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
