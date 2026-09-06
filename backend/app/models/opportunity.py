"""Job-search pipeline (#247): opportunities and their notes.

An ``Opportunity`` is one company/role thread the owner is pursuing — the
owner-facing counterpart of the recruiter-facing ``Interaction`` (#69). It
moves through explicit stages; every call/decision is a ``Note`` on its
timeline; inbox interactions can be promoted into / linked to one.
"""

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:  # pragma: no cover - typing-only import, avoids a cycle
    from app.models.interview import Interview

# Plain strings validated at the API layer (same rationale as #69's sources):
# stages are product vocabulary, not DB constraints — additive by design.
OPPORTUNITY_STAGES = (
    "lead",
    "contacted",
    "screening",
    "interviewing",
    "offer",
    "closed_won",
    "closed_lost",
)
OPPORTUNITY_SOURCES = ("recruiter_outreach", "self_applied", "referral", "discovery")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    company: Mapped[str] = mapped_column(String(200), nullable=False)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="lead")
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="recruiter_outreach"
    )

    recruiter_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recruiter_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    salary_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The idempotency key for promote-from-inbox (#279). A DB-level UNIQUE is
    # the only thing that survives two concurrent requests: promote runs
    # check-then-insert across SEPARATE sessions (get_db yields one per
    # request), so an application-level lookup races and a review reproduced
    # exactly that — two permanent cards for one interaction, with no DELETE to
    # undo them. Deliberately NOT derived from a note's interaction_id: notes
    # are admin-writable, which would make the key forgeable.
    promoted_from_interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True, unique=True
    )

    # Which CV variant went to this company, and when (#247 criterion 4).
    # SET NULL on delete: removing a CV version must never corrupt the
    # opportunity — the notes timeline keeps the human-readable record.
    sent_cv_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="SET NULL"), nullable=True
    )
    sent_cv_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    notes: Mapped[list["OpportunityNote"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="OpportunityNote.created_at.desc()",
    )
    # The interview calendar (#70 / phase 2) — soonest first, the order both the
    # opportunity detail view and the .ics export want.
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="Interview.scheduled_at.asc()",
    )

    __table_args__ = (
        Index("ix_opportunities_stage", "stage"),
        Index("ix_opportunities_updated_at", "updated_at"),
    )


class OpportunityNote(Base):
    __tablename__ = "opportunity_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    # Optional link back to the inbox item this note came from (#69).
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="notes")

    __table_args__ = (
        Index("ix_opportunity_notes_opportunity", "opportunity_id"),
        # The promote path filters notes by their source interaction.
        Index("ix_opportunity_notes_interaction_id", "interaction_id"),
    )
