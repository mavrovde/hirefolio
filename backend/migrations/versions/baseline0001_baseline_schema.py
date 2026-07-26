"""baseline schema

Consolidates the schema that had previously only ever been produced by
``Base.metadata.create_all`` (plus a handful of ad-hoc ``ALTER TABLE``
statements in ``app/main.py``) into a single, authoritative Alembic
revision. It creates every table/column/index/constraint that exists in
``app/models/`` today: ``users``, ``cv_documents``, ``cv_requests``,
``posts`` (including the LinkedIn provenance columns, the pgvector
``embedding`` column, and the partial unique index on ``source_urn``), and
``profile_snapshots``.

This replaces the previously disjoint/incomplete migration history (the
top-level ``migrations/00N_*.py`` scripts, which were never even on
Alembic's discovery path, and the ``migrations/versions/*`` chain, which
only contained incremental ``ALTER TABLE`` diffs assuming tables already
existed via ``create_all`` and therefore could never run against an empty
database). See GitHub issue #46 for the full history.

Revision ID: baseline0001
Revises:
Create Date: 2026-07-26 17:09:13.443035

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "baseline0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector must exist before the `posts.embedding` column can be created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "cv_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_table(
        "cv_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("position_description", sa.String(length=1000), nullable=True),
        sa.Column("subscribe_to_updates", sa.Boolean(), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("cv_version", sa.String(), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("image_blob", sa.LargeBinary(), nullable=True),
        sa.Column("image_type", sa.String(length=50), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_urn", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", "language", name="ux_post_slug_lang"),
    )
    op.create_index(
        "ix_post_source_urn_unique",
        "posts",
        ["source_urn"],
        unique=True,
        postgresql_where=sa.text("source_urn IS NOT NULL"),
    )
    op.create_index(op.f("ix_posts_language"), "posts", ["language"], unique=False)
    op.create_index(op.f("ix_posts_slug"), "posts", ["slug"], unique=False)
    op.create_table(
        "profile_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", "language", name="uq_profile_snapshot_language"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("gemini_api_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("profile_snapshots")
    op.drop_index(op.f("ix_posts_slug"), table_name="posts")
    op.drop_index(op.f("ix_posts_language"), table_name="posts")
    op.drop_index(
        "ix_post_source_urn_unique",
        table_name="posts",
        postgresql_where=sa.text("source_urn IS NOT NULL"),
    )
    op.drop_table("posts")
    op.drop_table("cv_requests")
    op.drop_table("cv_documents")
    # Extension intentionally left in place on downgrade (other objects may
    # depend on it; dropping shared extensions is a manual, deliberate step).
