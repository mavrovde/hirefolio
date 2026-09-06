"""Interview calendar API (#70 / #247 phase 2) — admin-only.

Scheduling, rescheduling and outcome tracking for the interviews on an
opportunity thread, plus the two surfaces the admin dashboard needs on day one:
an **upcoming** window across every opportunity and a per-interview **.ics**
export (RFC 5545) that imports into any calendar app.

Design notes worth keeping:

* Scheduling an interview moves the opportunity to ``interviewing`` — but only
  ever FORWARD. The same "never regress" rule the promote handler applies to an
  interaction's status (``opportunities.py``) applies here to the stage: a card
  already at ``offer`` or ``closed_won`` keeps its stage when a follow-up round
  is booked.
* Every schedule/reschedule/outcome/removal is mirrored onto the opportunity's
  notes timeline, which is where this pipeline keeps its history (phase 1's
  ``move_stage`` set that precedent). Deleting an interview therefore never
  loses the audit trail — see ``delete_interview``.
* Input follows the strip-then-validate contract of ``opportunities.py``:
  normalize first, THEN check bounds, so whitespace padding can neither satisfy
  a minimum nor be stored as a "value".
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logger import logger
from app.models.interview import INTERVIEW_KINDS, INTERVIEW_OUTCOMES, Interview
from app.models.opportunity import OPPORTUNITY_STAGES, Opportunity, OpportunityNote
from app.services.auth import get_current_admin_user
from app.services.email import EmailService
from app.services.ics import build_event_ics

# Interviews are reached two ways: nested under their opportunity (create/list)
# and directly by id (reschedule/outcome/remove/export/upcoming).
opportunity_router = APIRouter(
    prefix="/admin/opportunities",
    tags=["admin-interviews"],
    dependencies=[Depends(get_current_admin_user)],
)
router = APIRouter(
    prefix="/admin/interviews",
    tags=["admin-interviews"],
    dependencies=[Depends(get_current_admin_user)],
)

_INTERVIEWING_STAGE = "interviewing"
_INTERVIEWING_INDEX = OPPORTUNITY_STAGES.index(_INTERVIEWING_STAGE)


def _strip_str(v: object) -> object:
    """Strip strings before length validation; empty-after-strip becomes None
    (same normalizer contract as opportunities.py / interactions.py)."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class InterviewIn(BaseModel):
    scheduled_at: str = Field(min_length=1)  # ISO 8601, offset-aware preferred
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    kind: str = "video"
    location_or_link: str | None = Field(default=None, max_length=1000)
    interviewer: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=20_000)

    _strip = field_validator(
        "scheduled_at", "location_or_link", "interviewer", "notes", mode="before"
    )(_strip_str)


class InterviewPatch(BaseModel):
    """Partial update — only the keys actually sent are applied.

    ``model_dump(exclude_unset=True)`` is what makes "omitted" different from
    "explicitly null": omitting ``notes`` keeps it, sending ``null`` clears it.
    """

    scheduled_at: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    kind: str | None = None
    location_or_link: str | None = Field(default=None, max_length=1000)
    interviewer: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=20_000)
    outcome: str | None = None

    _strip = field_validator(
        "scheduled_at", "location_or_link", "interviewer", "notes", mode="before"
    )(_strip_str)


class InterviewOut(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    scheduled_at: str
    duration_minutes: int
    kind: str
    location_or_link: str | None
    interviewer: str | None
    notes: str | None
    outcome: str
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, iv: Interview) -> "InterviewOut":
        return cls(
            id=iv.id,
            opportunity_id=iv.opportunity_id,
            scheduled_at=iv.scheduled_at.isoformat(),
            duration_minutes=iv.duration_minutes,
            kind=iv.kind,
            location_or_link=iv.location_or_link,
            interviewer=iv.interviewer,
            notes=iv.notes,
            outcome=iv.outcome,
            created_at=iv.created_at.isoformat(),
            updated_at=iv.updated_at.isoformat(),
        )


class UpcomingInterviewOut(InterviewOut):
    """An upcoming slot carries its company/role so the dashboard needs no
    second round-trip per row."""

    company: str
    role_title: str
    stage: str

    @classmethod
    def from_row(cls, iv: Interview, opp: Opportunity) -> "UpcomingInterviewOut":
        return cls(
            **InterviewOut.from_model(iv).model_dump(),
            company=opp.company,
            role_title=opp.role_title,
            stage=opp.stage,
        )


def _validate_kind(kind: object) -> None:
    if kind not in INTERVIEW_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown interview kind '{kind}'")


def _validate_outcome(outcome: object) -> None:
    if outcome not in INTERVIEW_OUTCOMES:
        raise HTTPException(
            status_code=422, detail=f"Unknown interview outcome '{outcome}'"
        )


# Ceiling from InterviewIn/InterviewPatch (`duration_minutes: le=1440`). Kept
# beside the parser because the two MUST agree: the parser guarantees that
# DTEND is representable for every duration the schema will accept.
_MAX_INTERVIEW_DURATION = timedelta(minutes=1440)


def _parse_scheduled_at(value: str) -> datetime:
    """Parse an ISO-8601 instant and normalize it to UTC.

    A value without an offset is read as UTC rather than rejected (the admin UI
    always sends an offset; scripts and curl often don't), so what lands in the
    column is always one unambiguous instant.

    Non-string input never reaches here: the schema types the field as ``str``
    (pydantic rejects a number or a list with 422) and ``_reject_null`` rejects
    an explicit ``null`` — so there is no defensive isinstance branch to leave
    permanently untested.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="Invalid scheduled_at") from e
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    # OverflowError, not ValueError, is what an instant near datetime.max
    # raises — both when the offset shift crosses the boundary and later when
    # the exporter adds DTEND. Catching only ValueError turned
    # `9999-12-31T23:59:59-14:00` into an unhandled 500 instead of the
    # documented 422, and — the serious half — a value that survived the shift
    # was ACCEPTED with 201 and then raised on every `.ics` export, forever
    # (#289 review round 1).
    #
    # The bound is the MAXIMUM allowed duration, not this interview's: a PATCH
    # can raise the duration later, so anything accepted here must stay
    # exportable for any duration the schema permits.
    try:
        normalized = parsed.astimezone(UTC)
        normalized + _MAX_INTERVIEW_DURATION
    except OverflowError as e:
        raise HTTPException(
            status_code=422,
            detail="scheduled_at is outside the representable date range",
        ) from e
    return normalized


def _reject_null(data: dict[str, Any], *keys: str) -> None:
    """A PATCH may omit these keys, but may not blank them: they are NOT NULL
    columns, so an explicit ``null`` is a client bug, not a "clear it"."""
    for key in keys:
        if key in data and data[key] is None:
            raise HTTPException(status_code=422, detail=f"'{key}' cannot be null")


async def _get_opportunity_or_404(
    db: AsyncSession, opportunity_id: uuid.UUID
) -> Opportunity:
    opp = (
        (await db.execute(select(Opportunity).where(Opportunity.id == opportunity_id)))
        .scalars()
        .first()
    )
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


async def _get_interview_or_404(
    db: AsyncSession, interview_id: uuid.UUID
) -> tuple[Interview, Opportunity]:
    """Load an interview together with its opportunity in one round trip.

    Selected as an explicit pair rather than via ``Interview.opportunity``: a
    relationship attribute expires on commit and would lazy-load inside the
    async context afterwards (``greenlet_spawn has not been called``, §22).
    """
    row = (
        await db.execute(
            select(Interview, Opportunity)
            .join(Opportunity, Interview.opportunity_id == Opportunity.id)
            .where(Interview.id == interview_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return row[0], row[1]


def _advance_stage_to_interviewing(db: AsyncSession, opp: Opportunity) -> None:
    """Move the card to ``interviewing`` — forward only.

    Mirrors the promote handler's never-regress rule: booking a follow-up round
    on a card that already reached ``offer`` must not drag it backwards.
    """
    # A stage outside the known set is data drift, not a client error, and
    # `.index()` on it raised ValueError -> 500. Treat it as "do not touch":
    # silently rewriting an unrecognised stage would be worse than leaving it.
    if opp.stage not in OPPORTUNITY_STAGES:
        return
    if OPPORTUNITY_STAGES.index(opp.stage) >= _INTERVIEWING_INDEX:
        return
    db.add(
        OpportunityNote(
            opportunity_id=opp.id,
            body=f"Stage: {opp.stage} → {_INTERVIEWING_STAGE} (interview scheduled)",
        )
    )
    opp.stage = _INTERVIEWING_STAGE


@opportunity_router.post(
    "/{opportunity_id}/interviews", status_code=201, response_model=InterviewOut
)
async def schedule_interview(
    opportunity_id: uuid.UUID,
    body: InterviewIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    """Book a slot on an opportunity and advance its stage to `interviewing`."""
    _validate_kind(body.kind)
    scheduled_at = _parse_scheduled_at(body.scheduled_at)
    opp = await _get_opportunity_or_404(db, opportunity_id)

    interview = Interview(
        opportunity_id=opp.id,
        scheduled_at=scheduled_at,
        duration_minutes=body.duration_minutes,
        kind=body.kind,
        location_or_link=body.location_or_link,
        interviewer=body.interviewer,
        notes=body.notes,
        outcome="pending",
    )
    db.add(interview)
    db.add(
        OpportunityNote(
            opportunity_id=opp.id,
            body=(
                f"Interview scheduled: {body.kind} on "
                f"{scheduled_at.isoformat()} ({body.duration_minutes} min)"
            ),
        )
    )
    _advance_stage_to_interviewing(db, opp)
    await db.commit()
    await db.refresh(interview)
    # #247 criterion 3's reminder clause: owner email with the invite attached,
    # AFTER commit so the .ics reflects the persisted row. Background — a mail
    # failure must never fail the scheduling — and the service skips itself
    # when SMTP is unconfigured.
    background_tasks.add_task(
        _send_reminder,
        company=opp.company,
        role_title=opp.role_title,
        kind=interview.kind,
        scheduled_at_iso=interview.scheduled_at.isoformat(),
        duration_minutes=interview.duration_minutes,
        location_or_link=interview.location_or_link,
        interviewer=interview.interviewer,
        ics_payload=_interview_ics(interview, opp),
        rescheduled=False,
    )
    return InterviewOut.from_model(interview)


@opportunity_router.get(
    "/{opportunity_id}/interviews", response_model=list[InterviewOut]
)
async def list_interviews(
    opportunity_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[InterviewOut]:
    """Every interview on one opportunity, soonest first."""
    await _get_opportunity_or_404(db, opportunity_id)
    rows = (
        (
            await db.execute(
                select(Interview)
                .where(Interview.opportunity_id == opportunity_id)
                .order_by(Interview.scheduled_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [InterviewOut.from_model(iv) for iv in rows]


# Declared BEFORE "/{interview_id}…": Starlette matches routes in declaration
# order, so a later "/upcoming" would be swallowed by the UUID path param and
# answered with 422 instead of the dashboard's data.
@router.get("/upcoming", response_model=list[UpcomingInterviewOut])
async def upcoming_interviews(
    days: int = Query(default=14, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[UpcomingInterviewOut]:
    """Scheduled interviews across ALL opportunities within the next `days`.

    Cancelled slots are excluded — the dashboard asks "what do I have to
    prepare for", and a cancelled round is history, not a commitment.
    """
    now = datetime.now(UTC)
    # The row stays listed while it is STILL RUNNING — an interview that has
    # started but not finished is the most relevant row on a dashboard asking
    # "what am I in right now", and `scheduled_at >= now` dropped it the moment
    # it began (#289 review round 1). The predicate is per-row end time, not a
    # fixed lookback: a blanket `now - max duration` would resurrect interviews
    # that already ended, which an existing test correctly rejects.
    rows = (
        await db.execute(
            select(Interview, Opportunity)
            .join(Opportunity, Interview.opportunity_id == Opportunity.id)
            .where(
                Interview.scheduled_at
                + func.make_interval(0, 0, 0, 0, 0, Interview.duration_minutes)
                >= now,
                Interview.scheduled_at <= now + timedelta(days=days),
                Interview.outcome != "cancelled",
            )
            .order_by(Interview.scheduled_at.asc())
        )
    ).all()
    return [UpcomingInterviewOut.from_row(iv, opp) for iv, opp in rows]


def _interview_ics(interview: Interview, opp: Opportunity) -> str:
    """The ONE rendering of an interview as a VEVENT.

    Shared by the export route and the reminder email so the attachment a
    calendar imports and the file the admin downloads are the same event —
    same UID included, so importing both UPDATES rather than duplicates.
    """
    description = [
        (
            f"{interview.kind.capitalize()} interview for "
            f"{opp.role_title} at {opp.company}."
        )
    ]
    if interview.interviewer:
        description.append(f"Interviewer: {interview.interviewer}")
    if interview.notes:
        description.append(interview.notes)
    if opp.link:
        description.append(f"Job posting: {opp.link}")

    # A UID must be globally unique and stable across re-exports, so a calendar
    # UPDATES the event instead of duplicating it: row id @ the site's domain.
    host = urlparse(settings.site_url).hostname or "hirefolio"
    return build_event_ics(
        uid=f"{interview.id}@{host}",
        summary=f"Interview: {opp.company} — {opp.role_title}",
        start=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        description="\n".join(description),
        location=interview.location_or_link or "",
        cancelled=interview.outcome == "cancelled",
        dtstamp=interview.updated_at,
    )


def _send_reminder(
    *,
    company: str,
    role_title: str,
    kind: str,
    scheduled_at_iso: str,
    duration_minutes: int,
    location_or_link: str | None,
    interviewer: str | None,
    ics_payload: str,
    rescheduled: bool,
) -> None:
    """BackgroundTasks target — the interactions._notify idiom: a reminder
    failure must never surface into the API response that scheduled the round.
    The service itself already skips gracefully when SMTP is unconfigured."""
    try:
        EmailService().send_interview_reminder(
            company=company,
            role_title=role_title,
            kind=kind,
            scheduled_at_iso=scheduled_at_iso,
            duration_minutes=duration_minutes,
            location_or_link=location_or_link,
            interviewer=interviewer,
            ics_payload=ics_payload,
            rescheduled=rescheduled,
        )
    except Exception as e:
        logger.error(f"Interview reminder failed in background: {e}")


@router.get("/{interview_id}.ics", response_class=Response)
async def export_interview_ics(
    interview_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Response:
    """RFC 5545 VEVENT for one interview — importable into any calendar app."""
    interview, opp = await _get_interview_or_404(db, interview_id)
    body = _interview_ics(interview, opp)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="interview-{interview.id}.ics"'
            )
        },
    )


@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(
    interview_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InterviewOut:
    """One interview by id (the admin detail view's refresh target)."""
    interview, _opp = await _get_interview_or_404(db, interview_id)
    return InterviewOut.from_model(interview)


@router.patch("/{interview_id}", response_model=InterviewOut)
async def update_interview(
    interview_id: uuid.UUID,
    body: InterviewPatch,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    """Reschedule a slot and/or record its outcome."""
    data = body.model_dump(exclude_unset=True)
    _reject_null(data, "scheduled_at", "duration_minutes", "kind", "outcome")
    if "kind" in data:
        _validate_kind(data["kind"])
    if "outcome" in data:
        _validate_outcome(data["outcome"])

    interview, opp = await _get_interview_or_404(db, interview_id)

    rescheduled = False
    if "scheduled_at" in data:
        moved_to = _parse_scheduled_at(data["scheduled_at"])
        if moved_to != interview.scheduled_at:
            rescheduled = True
            db.add(
                OpportunityNote(
                    opportunity_id=opp.id,
                    body=(
                        f"Interview rescheduled: {interview.scheduled_at.isoformat()}"
                        f" → {moved_to.isoformat()}"
                    ),
                )
            )
        interview.scheduled_at = moved_to
    if "outcome" in data and data["outcome"] != interview.outcome:
        db.add(
            OpportunityNote(
                opportunity_id=opp.id,
                body=f"Interview outcome: {interview.outcome} → {data['outcome']}",
            )
        )
    for field in (
        "duration_minutes",
        "kind",
        "location_or_link",
        "interviewer",
        "notes",
        "outcome",
    ):
        if field in data:
            setattr(interview, field, data[field])

    await db.commit()
    # refresh, never a post-commit re-select: the identity map would hand back
    # the same object with stale, expired state (§22).
    await db.refresh(interview)
    # Only an actual MOVE re-notifies — recording an outcome or editing notes
    # is not calendar news, and a same-instant "reschedule" is a no-op.
    if rescheduled:
        background_tasks.add_task(
            _send_reminder,
            company=opp.company,
            role_title=opp.role_title,
            kind=interview.kind,
            scheduled_at_iso=interview.scheduled_at.isoformat(),
            duration_minutes=interview.duration_minutes,
            location_or_link=interview.location_or_link,
            interviewer=interview.interviewer,
            ics_payload=_interview_ics(interview, opp),
            rescheduled=True,
        )
    return InterviewOut.from_model(interview)


@router.delete("/{interview_id}", status_code=204)
async def delete_interview(
    interview_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Response:
    """Remove a slot that should never have existed (a typo, a duplicate).

    DELETE exists — rather than "cancel is the only way out" — because phase 1
    shipped no way to undo a mis-created row and reviewers flagged exactly that.
    It is not a history hole: the removal is written to the opportunity's notes
    timeline first, so the record of "there was a round here, and it went away"
    survives the row. To keep an interview that simply did not happen, PATCH its
    outcome to ``cancelled`` instead — that keeps it exportable as a CANCELLED
    VEVENT so calendars can drop it.
    """
    interview, opp = await _get_interview_or_404(db, interview_id)
    # Capture before the delete: touching an attribute after the commit that
    # removed the row would trigger a lazy refresh of a gone instance (§22).
    summary = (
        f"Interview removed: {interview.kind} on "
        f"{interview.scheduled_at.isoformat()} (outcome: {interview.outcome})"
    )
    db.add(OpportunityNote(opportunity_id=opp.id, body=summary))
    await db.delete(interview)
    await db.commit()
    return Response(status_code=204)
