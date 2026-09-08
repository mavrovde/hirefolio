"""Tailored application links (#250) — one unlisted page per application.

Two surfaces in one module because they are two halves of one contract:

* **admin** (`/admin/tailored-links`, auth-gated) mints and edits the links;
* **public** (`/for/{slug}`, no auth) serves the tailored view, records the
  visit, and hands over the pinned CV variant.

The slug IS the access control — there is no token and no login on the public
half — so the generated form carries a random suffix and disabled/expired
links are indistinguishable from unknown ones (both 404).
"""

import re
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.cv_document import CvDocument
from app.models.opportunity import Opportunity, OpportunityNote
from app.models.tailored_link import MAX_HIGHLIGHTS, TailoredLink
from app.services.auth import get_current_admin_user

admin_router = APIRouter(
    prefix="/admin/tailored-links",
    tags=["admin-tailored-links"],
    dependencies=[Depends(get_current_admin_user)],
)
public_router = APIRouter(prefix="/for", tags=["tailored-links"])

#: A slug is a URL path segment and nothing else: lowercase, digits, hyphens,
#: never leading/trailing hyphens. Validated here rather than only in the DB so
#: a bad custom slug is a 422 at the form, not a 500 at the route.
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SLUG_MAX_LENGTH = 120
#: Length of the random suffix on a generated slug. 36**8 ≈ 2.8e12 — the URL is
#: the only secret this feature has, so a guessable one is a data leak.
SLUG_SUFFIX_LENGTH = 8
_SLUG_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
#: Leaves room for `-` + the suffix inside SLUG_MAX_LENGTH.
_SLUG_STEM_MAX = SLUG_MAX_LENGTH - SLUG_SUFFIX_LENGTH - 1


def slugify(value: str) -> str:
    """Lowercase, hyphen-joined, ASCII-only stem of a free-text label."""
    stem = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return stem[:_SLUG_STEM_MAX].strip("-")


def generate_slug(company: str, role_title: str) -> str:
    """A readable stem plus an unguessable suffix (issue #250, action 5)."""
    stem = slugify(f"{company} {role_title}")
    suffix = "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(SLUG_SUFFIX_LENGTH))
    return f"{stem}-{suffix}" if stem else suffix


def _clean_highlights(values: list[str] | None) -> list[str]:
    """Strip, drop blanks, de-duplicate (case-insensitively), cap the length."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = raw.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            cleaned.append(item)
    return cleaned[:MAX_HIGHLIGHTS]


class TailoredLinkIn(BaseModel):
    opportunity_id: uuid.UUID
    #: Omitted → generated from the opportunity with a random suffix.
    slug: str | None = Field(default=None, max_length=SLUG_MAX_LENGTH)
    cv_document_id: uuid.UUID | None = None
    headline_note: str | None = Field(default=None, max_length=2000)
    highlighted_skills: list[str] = Field(default_factory=list)
    highlighted_projects: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None

    @field_validator("slug", "headline_note", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class TailoredLinkPatch(BaseModel):
    """Every field optional: the admin panel patches one control at a time.

    `None` means "leave alone" for the scalars the model also allows to BE
    null (`cv_document_id`, `expires_at`); clearing those is done with the
    explicit `clear_cv` / `clear_expiry` flags, because a JSON body cannot
    otherwise tell "absent" from "set to null".
    """

    enabled: bool | None = None
    cv_document_id: uuid.UUID | None = None
    clear_cv: bool = False
    headline_note: str | None = Field(default=None, max_length=2000)
    highlighted_skills: list[str] | None = None
    highlighted_projects: list[str] | None = None
    expires_at: datetime | None = None
    clear_expiry: bool = False


class TailoredLinkOut(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    slug: str
    path: str
    url: str
    cv_document_id: uuid.UUID | None
    cv_version: str | None
    cv_filename: str | None
    headline_note: str | None
    highlighted_skills: list[str]
    highlighted_projects: list[str]
    enabled: bool
    expires_at: str | None
    visit_count: int
    cv_download_count: int
    last_visited_at: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(
        cls, link: TailoredLink, cv: CvDocument | None = None
    ) -> "TailoredLinkOut":
        path = f"/for/{link.slug}"
        return cls(
            id=link.id,
            opportunity_id=link.opportunity_id,
            slug=link.slug,
            path=path,
            # The absolute URL the owner pastes into an application. Built from
            # the runtime SITE_URL (#65) so a forked deployment never has to
            # rebuild an image to get its own domain into the link.
            url=f"{settings.site_url.rstrip('/')}{path}",
            cv_document_id=link.cv_document_id,
            cv_version=cv.version if cv else None,
            cv_filename=cv.filename if cv else None,
            headline_note=link.headline_note,
            highlighted_skills=list(link.highlighted_skills or []),
            highlighted_projects=list(link.highlighted_projects or []),
            enabled=link.enabled,
            expires_at=link.expires_at.isoformat() if link.expires_at else None,
            visit_count=link.visit_count,
            cv_download_count=link.cv_download_count,
            last_visited_at=link.last_visited_at.isoformat()
            if link.last_visited_at
            else None,
            created_at=link.created_at.isoformat(),
            updated_at=link.updated_at.isoformat(),
        )


class TailoredViewOut(BaseModel):
    """The public payload — deliberately NOT the admin row.

    It carries what the tailored page renders and nothing else: no visit
    counters, no expiry, no opportunity id. The recipient must not be able to
    read the owner's own pipeline metrics out of a page meant for them.
    """

    slug: str
    company: str
    role_title: str
    headline_note: str | None
    highlighted_skills: list[str]
    highlighted_projects: list[str]
    cv_version: str | None
    #: Where the tailored CV CTA points, or `None` when no variant is pinned
    #: (the page then falls back to the site's normal CV flow).
    cv_download_path: str | None


async def _cv_map(
    db: AsyncSession, links: list[TailoredLink]
) -> dict[uuid.UUID, CvDocument]:
    """One query for every referenced CV variant (never N+1, never a lazy load
    on an async session — that raises a greenlet error, not a slow query)."""
    ids = {link.cv_document_id for link in links if link.cv_document_id}
    if not ids:
        return {}
    rows = (
        (await db.execute(select(CvDocument).where(CvDocument.id.in_(ids))))
        .scalars()
        .all()
    )
    return {row.id: row for row in rows}


async def _link_or_404(db: AsyncSession, link_id: uuid.UUID) -> TailoredLink:
    link = await db.get(TailoredLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Tailored link not found")
    return link


def _validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise HTTPException(
            status_code=422,
            detail="A slug may contain lowercase letters, digits and inner hyphens only",
        )


@admin_router.post("", status_code=201, response_model=TailoredLinkOut)
async def create_link(
    body: TailoredLinkIn, db: AsyncSession = Depends(get_db)
) -> TailoredLinkOut:
    opportunity = await db.get(Opportunity, body.opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    cv: CvDocument | None = None
    if body.cv_document_id is not None:
        cv = await db.get(CvDocument, body.cv_document_id)
        if cv is None:
            raise HTTPException(status_code=404, detail="CV document not found")

    if body.slug is not None:
        _validate_slug(body.slug)
        slug = body.slug
    else:
        slug = generate_slug(opportunity.company, opportunity.role_title)

    link = TailoredLink(
        slug=slug,
        opportunity_id=opportunity.id,
        cv_document_id=body.cv_document_id,
        headline_note=body.headline_note,
        highlighted_skills=_clean_highlights(body.highlighted_skills),
        highlighted_projects=_clean_highlights(body.highlighted_projects),
        expires_at=body.expires_at,
    )
    db.add(link)
    db.add(
        OpportunityNote(
            opportunity_id=opportunity.id,
            body=f"Tailored link created: /for/{slug}",
        )
    )
    try:
        # The UNIQUE on `slug` rejects at FLUSH: a duplicate custom slug is a
        # 409 the form can act on, never a 500 (and never a silent overwrite
        # of somebody else's application page).
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="That slug is already taken"
        ) from exc
    await db.refresh(link)
    return TailoredLinkOut.from_model(link, cv)


@admin_router.get("", response_model=list[TailoredLinkOut])
async def list_links(
    opportunity_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[TailoredLinkOut]:
    query = select(TailoredLink).order_by(TailoredLink.created_at.desc())
    if opportunity_id is not None:
        query = query.where(TailoredLink.opportunity_id == opportunity_id)
    links = list((await db.execute(query)).scalars().all())
    cvs = await _cv_map(db, links)
    return [
        TailoredLinkOut.from_model(
            link, cvs.get(link.cv_document_id) if link.cv_document_id else None
        )
        for link in links
    ]


@admin_router.patch("/{link_id}", response_model=TailoredLinkOut)
async def update_link(
    link_id: uuid.UUID, body: TailoredLinkPatch, db: AsyncSession = Depends(get_db)
) -> TailoredLinkOut:
    link = await _link_or_404(db, link_id)

    if body.enabled is not None:
        link.enabled = body.enabled
    if body.headline_note is not None:
        note = body.headline_note.strip()
        link.headline_note = note or None
    if body.highlighted_skills is not None:
        link.highlighted_skills = _clean_highlights(body.highlighted_skills)
    if body.highlighted_projects is not None:
        link.highlighted_projects = _clean_highlights(body.highlighted_projects)

    cv: CvDocument | None = None
    if body.clear_cv:
        link.cv_document_id = None
    elif body.cv_document_id is not None:
        cv = await db.get(CvDocument, body.cv_document_id)
        if cv is None:
            raise HTTPException(status_code=404, detail="CV document not found")
        link.cv_document_id = cv.id

    if body.clear_expiry:
        link.expires_at = None
    elif body.expires_at is not None:
        link.expires_at = body.expires_at

    await db.commit()
    await db.refresh(link)
    if cv is None and link.cv_document_id is not None:
        cv = await db.get(CvDocument, link.cv_document_id)
    return TailoredLinkOut.from_model(link, cv)


@admin_router.delete("/{link_id}", status_code=204)
async def delete_link(link_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    link = await _link_or_404(db, link_id)
    await db.delete(link)
    await db.commit()


async def _live_link_or_404(db: AsyncSession, slug: str) -> TailoredLink:
    """Resolve a public slug, or 404.

    Unknown, disabled and expired all produce the SAME 404 on purpose: a
    distinguishable response would confirm that a guessed slug exists.
    """
    link = (
        (await db.execute(select(TailoredLink).where(TailoredLink.slug == slug)))
        .scalars()
        .first()
    )
    if link is None or not link.is_live(datetime.now(UTC)):
        raise HTTPException(status_code=404, detail="Tailored link not found")
    return link


@public_router.get("/{slug}", response_model=TailoredViewOut)
async def get_tailored_view(
    slug: str, db: AsyncSession = Depends(get_db)
) -> TailoredViewOut:
    link = await _live_link_or_404(db, slug)
    opportunity = await db.get(Opportunity, link.opportunity_id)
    if opportunity is None:  # pragma: no cover - FK CASCADE removes the link too
        raise HTTPException(status_code=404, detail="Tailored link not found")
    cv = (
        await db.get(CvDocument, link.cv_document_id)
        if link.cv_document_id is not None
        else None
    )
    return TailoredViewOut(
        slug=link.slug,
        company=opportunity.company,
        role_title=opportunity.role_title,
        headline_note=link.headline_note,
        highlighted_skills=list(link.highlighted_skills or []),
        highlighted_projects=list(link.highlighted_projects or []),
        cv_version=cv.version if cv else None,
        # A since-deleted variant (FK SET NULL) degrades to the normal CV flow
        # instead of advertising a download that would 404.
        cv_download_path=f"{settings.api_prefix}/for/{link.slug}/cv" if cv else None,
    )


async def _record(
    db: AsyncSession, link: TailoredLink, column: str, template: str
) -> None:
    """Bump one counter atomically and write the opportunity's timeline entry.

    The increment is a single UPDATE (`col = col + 1 RETURNING col`) rather
    than a read-modify-write: two recruiters opening the same link in the same
    second must produce two visits, and a Python-side `+= 1` across two
    sessions loses one of them.
    """
    # Read every attribute BEFORE expiring the instance: on an async session a
    # lazy re-load raises a greenlet error, not a slow query.
    link_id, opportunity_id, slug = link.id, link.opportunity_id, link.slug
    now = datetime.now(UTC)
    values: dict[str, object] = {column: getattr(TailoredLink, column) + 1}
    if column == "visit_count":
        values["last_visited_at"] = now
    count = (
        await db.execute(
            update(TailoredLink)
            .where(TailoredLink.id == link_id)
            .values(**values)
            .returning(getattr(TailoredLink, column))
        )
    ).scalar_one()
    # A core UPDATE leaves the already-loaded ORM instance stale in the
    # identity map, so the NEXT `select()` on the same session hands back the
    # old counter (lessons §22). Per-request sessions hide it in production and
    # a shared session does not — expiring keeps both honest.
    db.expire(link)
    db.add(
        OpportunityNote(
            opportunity_id=opportunity_id,
            body=template.format(slug=slug, count=count),
        )
    )
    await db.commit()


@public_router.post("/{slug}/visit", status_code=204)
async def record_visit(slug: str, db: AsyncSession = Depends(get_db)) -> None:
    """Count one opening of a tailored link (#250 criterion 4).

    Called from the BROWSER only: during SSR the same page is rendered by the
    server, and counting there would double every real visit (and count every
    crawler prefetch as a recruiter reading the page).
    """
    link = await _live_link_or_404(db, slug)
    await _record(
        db, link, "visit_count", "Tailored link /for/{slug} opened (visit #{count})"
    )


@public_router.get("/{slug}/cv")
async def download_tailored_cv(slug: str, db: AsyncSession = Depends(get_db)):
    """Serve the CV variant pinned to this link (#250 criterion 1/2).

    Deliberately NOT the active public CV: the whole point of a tailored link
    is that this recruiter gets the version written for this role.
    """
    link = await _live_link_or_404(db, slug)
    cv = (
        await db.get(CvDocument, link.cv_document_id)
        if link.cv_document_id is not None
        else None
    )
    if cv is None:
        raise HTTPException(status_code=404, detail="CV_ERROR_UNAVAILABLE")
    await _record(
        db,
        link,
        "cv_download_count",
        "Tailored link /for/{slug} CV downloaded (#{count})",
    )
    return Response(
        content=cv.data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv.filename}"'},
    )
