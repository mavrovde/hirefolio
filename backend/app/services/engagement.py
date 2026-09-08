"""Engagement analytics: recording, aggregation, retention, digest (#249).

One module owns the whole lifecycle of an ``EngagementEvent`` so the API layer
stays thin and the digest and the dashboard count the SAME thing — a second
copy of the aggregation is how two numbers start disagreeing.

Recording is deliberately best-effort: analytics must never change the outcome
of the flow it observes. ``record_event`` therefore writes through its OWN
session rather than the request's, and swallows its own failures.

WHY ITS OWN SESSION (this was a measured bug, not a preference): sharing the
caller's session makes "best effort" a lie. A failed event write has to
``rollback()``, and ``Session.rollback()`` is session-WIDE — it expires every
ORM object in the caller's identity map, so the caller's next attribute read
(``interaction.id``, ``active_cv.version``) becomes a lazy reload, i.e. sync IO
in an async context: ``MissingGreenlet``, and a 500 on a request that had
already succeeded. Owning the session makes the isolation structural instead of
asking every call site to remember it.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

import app.database
from app.config import settings
from app.logger import logger
from app.models.cv_request import CvRequest
from app.models.engagement_event import ENGAGEMENT_KINDS, EngagementEvent
from app.models.interaction import Interaction
from app.services.email import email_service

# Which source table resolves the display label of a feed row (see
# ``recent_events``). The event itself stores no identity data — the label is
# read back from the record it points at, at render time, for the admin only.
_CV_KINDS = ("cv_request", "cv_download")


async def record_event(
    kind: str,
    *,
    subject_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Record one engagement event. Returns True when a row was written.

    ``False`` means "deliberately not recorded" (flag off) or "recording
    failed" — never a reason for the caller to fail. An unknown ``kind`` is a
    programming error, not a runtime condition, so it raises: a typo must not
    become a silent bucket nobody ever counts.

    Takes no session on purpose (see the module docstring): it opens a
    short-lived one of its own, so neither its commit nor its rollback can
    reach the request's transaction or identity map. ``app.database`` is
    referenced through the module, not imported by name, so the test suite's
    session redirect reaches this write too.
    """
    if kind not in ENGAGEMENT_KINDS:
        raise ValueError(f"Unknown engagement kind '{kind}'")
    if not settings.engagement_analytics_enabled:
        return False
    try:
        async with app.database.async_session() as session:
            session.add(
                EngagementEvent(kind=kind, subject_id=subject_id, payload=payload)
            )
            await session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to record engagement event '{kind}': {e}")
        return False


def _zero_counts() -> dict[str, int]:
    return dict.fromkeys(ENGAGEMENT_KINDS, 0)


async def totals(db: AsyncSession) -> dict[str, int]:
    """All-time count per kind, with every known kind present (zero included).

    A missing key and a zero are the same fact; always emitting the full set
    keeps the dashboard from having to guess.
    """
    rows = (
        await db.execute(
            select(EngagementEvent.kind, func.count(EngagementEvent.id)).group_by(
                EngagementEvent.kind
            )
        )
    ).all()
    counts = _zero_counts()
    for kind, count in rows:
        counts[kind] = int(count)
    return counts


async def counts_since(db: AsyncSession, since: datetime) -> dict[str, int]:
    """Count per kind for events at or after ``since`` — the digest's window."""
    rows = (
        await db.execute(
            select(EngagementEvent.kind, func.count(EngagementEvent.id))
            .where(EngagementEvent.created_at >= since)
            .group_by(EngagementEvent.kind)
        )
    ).all()
    counts = _zero_counts()
    for kind, count in rows:
        counts[kind] = int(count)
    return counts


def week_start(moment: datetime) -> date:
    """Monday of ``moment``'s week, in UTC — the trend's bucket key."""
    day = moment.astimezone(UTC).date()
    return day - timedelta(days=day.weekday())


async def weekly_trend(db: AsyncSession, weeks: int) -> list[dict[str, Any]]:
    """Per-week counts per kind for the last ``weeks`` weeks, oldest first.

    Empty weeks are emitted as zeros so a chart has a continuous axis instead
    of silently collapsing a quiet fortnight.

    ``AT TIME ZONE 'UTC'`` is load-bearing: ``date_trunc('week', <timestamptz>)``
    truncates in the SESSION timezone, so the same row would land in different
    buckets on a server configured for Europe/Berlin. Pinning UTC makes the
    bucket boundary a property of the data, not of the deployment.
    """
    first = week_start(datetime.now(UTC)) - timedelta(weeks=weeks - 1)
    window_start = datetime.combine(first, time.min, tzinfo=UTC)
    bucket_expr = func.date_trunc(
        "week", EngagementEvent.created_at.op("AT TIME ZONE")("UTC")
    )
    rows = (
        await db.execute(
            select(
                bucket_expr.label("wk"),
                EngagementEvent.kind,
                func.count(EngagementEvent.id),
            )
            .where(EngagementEvent.created_at >= window_start)
            .group_by("wk", EngagementEvent.kind)
        )
    ).all()

    buckets: dict[date, dict[str, int]] = {
        first + timedelta(weeks=i): _zero_counts() for i in range(weeks)
    }
    for bucket, kind, count in rows:
        # A future-dated row (clock skew on the writer) passes the window
        # filter but has no bucket; it is counted in `totals`, not charted.
        target = buckets.get(bucket.date())
        if target is not None:
            target[kind] = int(count)
    return [
        {"week_start": day.isoformat(), "counts": counts}
        for day, counts in sorted(buckets.items())
    ]


def _display_label(name: str, company: str | None) -> str:
    """ONE definition of a feed row's label, shared by both source tables — two
    copies of this ternary would be two coverage branches and, eventually, two
    different formats."""
    return f"{name} ({company})" if company else name


async def _labels_for(
    db: AsyncSession, events: list[EngagementEvent]
) -> dict[uuid.UUID, str]:
    """Resolve display labels from the SOURCE records (never from the event).

    Two batched queries, not one per row: the feed is a list.
    """
    cv_ids = {
        e.subject_id for e in events if e.kind in _CV_KINDS and e.subject_id is not None
    }
    interaction_ids = {
        e.subject_id
        for e in events
        if e.kind not in _CV_KINDS and e.subject_id is not None
    }
    labels: dict[uuid.UUID, str] = {}
    if cv_ids:
        rows = (
            await db.execute(
                select(CvRequest.id, CvRequest.name, CvRequest.company).where(
                    CvRequest.id.in_(cv_ids)
                )
            )
        ).all()
        for row_id, name, company in rows:
            labels[row_id] = _display_label(name, company)
    if interaction_ids:
        interaction_rows = (
            await db.execute(
                select(Interaction.id, Interaction.name, Interaction.company).where(
                    Interaction.id.in_(interaction_ids)
                )
            )
        ).all()
        for row_id, name, company in interaction_rows:
            labels[row_id] = _display_label(name, company)
    return labels


async def recent_events(db: AsyncSession, limit: int) -> list[dict[str, Any]]:
    """Newest-first activity feed, each row labelled from its source record."""
    events = list(
        (
            await db.execute(
                select(EngagementEvent)
                .order_by(EngagementEvent.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    labels = await _labels_for(db, events)
    return [
        {
            "id": e.id,
            "kind": e.kind,
            "subject_id": e.subject_id,
            # None when the source record is gone (or never existed): the
            # event still counts, it just has nobody to name.
            "label": labels.get(e.subject_id) if e.subject_id else None,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


async def purge_old_events(db: AsyncSession) -> int:
    """Delete events older than the retention window; returns the row count.

    ``engagement_retention_days = 0`` keeps nothing (cutoff = now); a NEGATIVE
    value disables purging. Only events are deleted — the ``CvRequest`` /
    ``Interaction`` records they point at are never touched.
    """
    days = settings.engagement_retention_days
    if days < 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        delete(EngagementEvent).where(EngagementEvent.created_at < cutoff)
    )
    await db.commit()
    # A DELETE always yields a CursorResult; `Result` (the declared return type
    # of `execute`) is the wider base that does not carry `rowcount`.
    return int(cast("CursorResult[Any]", result).rowcount)


async def send_weekly_digest(db: AsyncSession) -> bool:
    """Email the owner a one-week engagement summary.

    Returns False when SMTP is unconfigured — the email service already treats
    that as "skip quietly", so an unconfigured host simply never sends.

    ``smtplib`` is blocking and time-bounded by ``smtp_timeout_seconds``; the
    send therefore runs off the event loop, exactly like the other blocking IO
    this app performs from a coroutine.
    """
    since = datetime.now(UTC) - timedelta(days=7)
    counts = await counts_since(db, since)
    return await asyncio.to_thread(
        email_service.send_engagement_digest, counts=counts, since=since
    )
