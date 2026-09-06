"""Job-search pipeline API (#247, phase 1) — admin-only.

CRUD for opportunities, a notes timeline, stage moves, and one-click
promotion of an inbox interaction (#69) into an opportunity.
"""

import uuid
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.interaction import Interaction
from app.models.opportunity import (
    OPPORTUNITY_SOURCES,
    OPPORTUNITY_STAGES,
    Opportunity,
    OpportunityNote,
)
from app.services.auth import get_current_admin_user

router = APIRouter(
    prefix="/admin/opportunities",
    tags=["admin-opportunities"],
    dependencies=[Depends(get_current_admin_user)],
)


def _strip_str(v: object) -> object:
    """Strip strings before length validation; empty-after-strip optional
    fields become None (mirrors interactions.py's normalizers)."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class OpportunityIn(BaseModel):
    # Same normalization contract as the public ContactRequest (interactions.py):
    # strip first, THEN validate — whitespace padding must not satisfy a minimum
    # and a blank card must be impossible (phase 1 has no DELETE to undo one).
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    stage: str = "lead"
    source: str = "recruiter_outreach"
    recruiter_name: str | None = Field(default=None, max_length=200)
    recruiter_email: str | None = Field(default=None, max_length=320)
    link: str | None = Field(default=None, max_length=1000)
    salary_note: str | None = Field(default=None, max_length=500)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_date: str | None = None  # ISO date

    _strip = field_validator(
        "company",
        "role_title",
        "recruiter_name",
        "link",
        "salary_note",
        "next_action",
        mode="before",
    )(_strip_str)


class NoteOut(BaseModel):
    id: uuid.UUID
    interaction_id: uuid.UUID | None
    body: str
    created_at: str


class OpportunityOut(BaseModel):
    id: uuid.UUID
    company: str
    role_title: str
    stage: str
    source: str
    recruiter_name: str | None
    recruiter_email: str | None
    link: str | None
    salary_note: str | None
    next_action: str | None
    next_action_date: str | None
    created_at: str
    updated_at: str
    notes: list[NoteOut] = []

    @classmethod
    def from_model(cls, o: Opportunity, with_notes: bool = False) -> "OpportunityOut":
        return cls(
            id=o.id,
            company=o.company,
            role_title=o.role_title,
            stage=o.stage,
            source=o.source,
            recruiter_name=o.recruiter_name,
            recruiter_email=o.recruiter_email,
            link=o.link,
            salary_note=o.salary_note,
            next_action=o.next_action,
            next_action_date=o.next_action_date.isoformat()
            if o.next_action_date
            else None,
            created_at=o.created_at.isoformat(),
            updated_at=o.updated_at.isoformat(),
            notes=[
                NoteOut(
                    id=n.id,
                    interaction_id=n.interaction_id,
                    body=n.body,
                    created_at=n.created_at.isoformat(),
                )
                for n in o.notes
            ]
            if with_notes
            else [],
        )


class OpportunityPage(BaseModel):
    items: list[OpportunityOut]
    total: int
    page: int
    pages: int


class StagePatch(BaseModel):
    stage: str


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    interaction_id: uuid.UUID | None = None

    _strip = field_validator("body", mode="before")(_strip_str)


class PromoteIn(BaseModel):
    interaction_id: uuid.UUID
    company: str | None = Field(default=None, max_length=200)
    role_title: str | None = Field(default=None, max_length=200)

    _strip = field_validator("company", "role_title", mode="before")(_strip_str)


def _validate_stage(stage: str) -> None:
    if stage not in OPPORTUNITY_STAGES:
        raise HTTPException(status_code=422, detail=f"Unknown stage '{stage}'")


def _parse_date(value: str | None):
    if value is None:
        return None
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="Invalid next_action_date") from e


async def _get_or_404(db: AsyncSession, opportunity_id: uuid.UUID) -> Opportunity:
    opp = (
        (
            await db.execute(
                select(Opportunity)
                .options(selectinload(Opportunity.notes))
                .where(Opportunity.id == opportunity_id)
            )
        )
        .scalars()
        .first()
    )
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.post("", status_code=201, response_model=OpportunityOut)
async def create_opportunity(
    body: OpportunityIn, db: AsyncSession = Depends(get_db)
) -> OpportunityOut:
    _validate_stage(body.stage)
    if body.source not in OPPORTUNITY_SOURCES:
        raise HTTPException(status_code=422, detail=f"Unknown source '{body.source}'")
    opp = Opportunity(
        company=body.company,
        role_title=body.role_title,
        stage=body.stage,
        source=body.source,
        recruiter_name=body.recruiter_name,
        recruiter_email=body.recruiter_email,
        link=body.link,
        salary_note=body.salary_note,
        next_action=body.next_action,
        next_action_date=_parse_date(body.next_action_date),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return OpportunityOut.from_model(opp)


@router.get("", response_model=OpportunityPage)
async def list_opportunities(
    stage: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> OpportunityPage:
    if stage is not None:
        _validate_stage(stage)
    query = select(Opportunity)
    count_query = select(func.count(Opportunity.id))
    if stage is not None:
        query = query.where(Opportunity.stage == stage)
        count_query = count_query.where(Opportunity.stage == stage)
    total = (await db.execute(count_query)).scalar_one()
    rows = (
        (
            await db.execute(
                query.order_by(Opportunity.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return OpportunityPage(
        items=[OpportunityOut.from_model(o) for o in rows],
        total=total,
        page=page,
        pages=max(1, ceil(total / page_size)),
    )


@router.get("/{opportunity_id}", response_model=OpportunityOut)
async def get_opportunity(
    opportunity_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> OpportunityOut:
    opp = await _get_or_404(db, opportunity_id)
    return OpportunityOut.from_model(opp, with_notes=True)


@router.patch("/{opportunity_id}/stage", response_model=OpportunityOut)
async def move_stage(
    opportunity_id: uuid.UUID, body: StagePatch, db: AsyncSession = Depends(get_db)
) -> OpportunityOut:
    _validate_stage(body.stage)
    opp = await _get_or_404(db, opportunity_id)
    if body.stage != opp.stage:
        # Stage history lives on the timeline, not in a separate table.
        db.add(
            OpportunityNote(
                opportunity_id=opp.id,
                body=f"Stage: {opp.stage} → {body.stage}",
            )
        )
        opp.stage = body.stage
        await db.commit()
        # Re-select alone would hit the identity map and keep the stale,
        # already-loaded (empty) notes collection — refresh reloads it.
        await db.refresh(opp, attribute_names=["notes", "stage", "updated_at"])
    return OpportunityOut.from_model(opp, with_notes=True)


@router.post("/{opportunity_id}/notes", status_code=201, response_model=OpportunityOut)
async def add_note(
    opportunity_id: uuid.UUID, body: NoteIn, db: AsyncSession = Depends(get_db)
) -> OpportunityOut:
    opp = await _get_or_404(db, opportunity_id)
    db.add(
        OpportunityNote(
            opportunity_id=opp.id,
            interaction_id=body.interaction_id,
            body=body.body,
        )
    )
    await db.commit()
    # Identity-map trap: see move_stage — the relationship must be refreshed.
    await db.refresh(opp, attribute_names=["notes", "updated_at"])
    return OpportunityOut.from_model(opp, with_notes=True)


# #278: an interaction's ORIGIN must survive promotion — hardcoding
# "recruiter_outreach" mislabelled every cv_request and booking, corrupting the
# one dimension the pipeline exists to measure (funnel analytics, #249).
# Explicit table, not a guess: a cv_request is the candidate being discovered
# through their own site, a booking is the same discovery with a slot attached.
INTERACTION_TO_OPPORTUNITY_SOURCE = {
    "contact_form": "recruiter_outreach",
    "cv_request": "discovery",
    "booking": "discovery",
}


@router.post("/promote", status_code=201, response_model=OpportunityOut)
async def promote_interaction(
    body: PromoteIn, db: AsyncSession = Depends(get_db)
) -> OpportunityOut:
    """One-click: an inbox interaction (#69) becomes an opportunity, with the
    original message preserved as the first timeline note."""
    interaction = (
        (
            await db.execute(
                select(Interaction).where(Interaction.id == body.interaction_id)
            )
        )
        .scalars()
        .first()
    )
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # #279: promoting is IDEMPOTENT per interaction. A double-click (or a
    # retried request) previously minted a second card, and phase 1 ships no
    # DELETE to undo one. The first promotion's timeline note carries the link,
    # so it is also the lookup key.
    existing = (
        (
            await db.execute(
                select(Opportunity)
                .join(OpportunityNote)
                .where(OpportunityNote.interaction_id == interaction.id)
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        await db.refresh(existing, attribute_names=["notes"])
        return OpportunityOut.from_model(existing, with_notes=True)

    opp = Opportunity(
        company=body.company or interaction.company or "Unknown company",
        role_title=body.role_title or "Unknown role",
        stage="lead",
        source=INTERACTION_TO_OPPORTUNITY_SOURCE.get(
            interaction.source, "recruiter_outreach"
        ),
        recruiter_name=interaction.name,
        recruiter_email=interaction.email,
    )
    db.add(opp)
    await db.flush()
    db.add(
        OpportunityNote(
            opportunity_id=opp.id,
            interaction_id=interaction.id,
            body=f"Promoted from inbox ({interaction.source}):\n{interaction.message}",
        )
    )
    if interaction.status == "new":
        interaction.status = "in_progress"
    await db.commit()
    # #277: refresh the loaded object instead of re-selecting — a post-commit
    # re-select returns the SAME identity-mapped instance with its stale
    # collection (lessons §22); it only "worked" here because notes was never
    # loaded before the commit.
    await db.refresh(opp, attribute_names=["notes"])
    return OpportunityOut.from_model(opp, with_notes=True)
