from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.config import settings
from app.database import Base


def utc_now():
    return datetime.now(UTC)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("slug", "language", name="ux_post_slug_lang"),
        Index(
            "ix_post_source_urn_unique",
            "source_urn",
            unique=True,
            postgresql_where=text("source_urn IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_blob: Mapped[bytes | None] = deferred(
        mapped_column(LargeBinary, nullable=True)
    )
    image_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="en", index=True)

    @property
    def display_image_url(self) -> str | None:
        if self.image_type:
            return f"{settings.api_prefix}/posts/{self.id}/image"
        return self.image_url

    published: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # LinkedIn provenance (nullable; unique index on source_urn when not null)
    source_urn: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Vector embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )
