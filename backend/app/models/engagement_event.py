"""First-party engagement events (#249).

WHY A TABLE AND NOT AN AGGREGATE OF EXISTING ROWS: most of what the dashboard
shows *could* be counted from the records that already exist — except the one
signal the feature is actually for. ``CvRequest.download_count`` /
``downloaded_at`` collapse an unbounded number of downloads into a counter plus
the LAST timestamp, so "Acme opened the CV twice on Tuesday and again today" is
unrecoverable: a per-week download trend cannot be derived from them. A repeated
event needs one row per occurrence.

PRIVACY: an event never duplicates identity data. It carries a ``kind``, a
``subject_id`` pointing at the record that already holds the identity
(``cv_requests.id`` / ``interactions.id``), and an optional non-identifying
``payload`` (e.g. the CV version). No IP, no user agent, no name/email. That is
also what makes retention safe to enforce here (see
``app.services.engagement.purge_old_events``): purging events destroys no
recruiter record.

EXTENSIBLE BY DESIGN: ``kind`` is a plain validated string, not a DB enum, so
future sources (tailored-link visits, bookings) are additive.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# The kinds this release emits. Validated at the write boundary
# (``record_event``) so a typo never becomes a silent, uncountable bucket.
ENGAGEMENT_KINDS = ("cv_request", "cv_download", "contact_submitted")

# Human wording for the owner-facing surfaces, so the digest email and the
# dashboard name the same event the same way. Derived from the key when a kind
# has no entry yet — a new kind must never be able to break the digest.
ENGAGEMENT_LABELS = {
    "cv_request": "CV requests",
    "cv_download": "CV downloads",
    "contact_submitted": "Contact submissions",
}


def engagement_label(kind: str) -> str:
    return ENGAGEMENT_LABELS.get(kind, kind.replace("_", " ").capitalize())


class EngagementEvent(Base):
    __tablename__ = "engagement_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    # Pointer to the source's domain record; nullable because a future source
    # may have none. Deliberately NOT a FK: an event must survive the deletion
    # of its source record (the counts stay honest), and the two tables have
    # different retention policies.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Non-identifying extras only (cv version, ...).
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        # The dashboard reads newest-first and groups by week + kind.
        Index("ix_engagement_events_created_at", "created_at"),
        Index("ix_engagement_events_kind", "kind"),
    )
