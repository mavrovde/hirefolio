"""Interview calendar (#70 / #247 phase 2).

An ``Interview`` is one scheduled conversation on an ``Opportunity`` thread —
the concrete event behind the ``interviewing`` stage. It carries everything a
calendar entry needs (when, how long, what kind, where/what link, with whom)
plus the owner-facing outcome, so the admin dashboard can answer "what is
coming up this fortnight" and export any slot as an ``.ics`` file.

Interviews hang off an opportunity with ``ON DELETE CASCADE``: an opportunity
thread that is deleted takes its schedule with it — a slot without its company
context is noise.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.opportunity import Opportunity

# Plain strings validated at the API layer, exactly like OPPORTUNITY_STAGES and
# #69's INTERACTION_SOURCES: this vocabulary is product wording, not a DB
# constraint, so adding a kind later is additive and needs no migration.
INTERVIEW_KINDS = ("phone", "video", "onsite", "other")
INTERVIEW_OUTCOMES = ("pending", "passed", "failed", "cancelled")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )

    # Stored in UTC (timestamptz); the API accepts any ISO-8601 offset and
    # normalizes, so a slot booked as 14:00+02:00 is one instant, not a string.
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="video")
    location_or_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    interviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="interviews")

    __table_args__ = (
        Index("ix_interviews_opportunity", "opportunity_id"),
        # The dashboard's "upcoming" window is a range scan on this column.
        Index("ix_interviews_scheduled_at", "scheduled_at"),
    )
