"""Tailored application links (#250).

One unlisted URL per application: the owner mints ``/for/<slug>`` from an
opportunity (#247), pins the CV variant that went with it, writes a note to
that recruiter and marks the skills/experience worth reading first. Opening
the link bumps a counter and lands on the opportunity's own timeline, so an
application stops being write-only.

Design notes that are NOT obvious from the columns:

* ``slug`` is the whole access control. There is no token and no login — the
  URL is the secret — so the generated form carries a random suffix
  (``app.api.tailored_links.generate_slug``) and the column is UNIQUE so two
  applications can never collide onto one page.
* ``cv_document_id`` is ``SET NULL`` on delete for the same reason as
  ``Opportunity.sent_cv_id``: deleting a CV version must degrade the link to
  the site's normal CV flow, never 500 it or orphan the row.
* ``opportunity_id`` is ``CASCADE``: a link has no meaning without the
  application it belongs to.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: Upper bound on the highlight arrays. A tailored page that "highlights"
#: forty skills highlights nothing, and an unbounded JSON array is an
#: unbounded write from an authenticated-but-fat-fingered admin form.
MAX_HIGHLIGHTS = 20


class TailoredLink(Base):
    __tablename__ = "tailored_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    cv_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="SET NULL"), nullable=True
    )

    headline_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain string arrays: they are matched case-insensitively against the
    # profile's own skills/experience at render time, never joined in SQL.
    highlighted_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    highlighted_projects: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cv_download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_visited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        # The admin detail panel lists a single opportunity's links.
        Index("ix_tailored_links_opportunity", "opportunity_id"),
    )

    def is_live(self, now: datetime) -> bool:
        """Whether the public route may serve this link right now.

        Disabled and expired are ONE public outcome (404): telling a visitor
        which of the two applies would leak that the slug exists.
        """
        if not self.enabled:
            return False
        return self.expires_at is None or self.expires_at > now
