"""Runtime key/value site settings (#271).

Site IDENTITY is env-driven on purpose (#65 — rebrand a prebuilt image with
env alone). This table exists for the settings that must change WITHOUT a
redeploy — the first being `availability`, which the owner flips from the
admin panel as their job search moves. A generic KV keeps the migration
surface flat; each key's allowed values are validated at its endpoint, not
here, so the table never encodes feature knowledge.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
