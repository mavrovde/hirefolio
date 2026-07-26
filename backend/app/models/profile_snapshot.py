from datetime import datetime, timezone
import uuid

from sqlalchemy import String, DateTime, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProfileSnapshot(Base):
    """A versioned, per-language snapshot of the profile.

    Stores the raw scraper `profile_data.json` as-is (``data``) so the site can
    render whatever fields exist. Versioning mirrors the CV pattern: exactly one
    row per language is ``is_active`` at a time — uploading a new version (or
    activating an existing one) deactivates the others *for that language only*,
    so EN and DE evolve independently (multilanguage).
    """

    __tablename__ = "profile_snapshots"
    __table_args__ = (
        UniqueConstraint("version", "language", name="uq_profile_snapshot_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="en")
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
