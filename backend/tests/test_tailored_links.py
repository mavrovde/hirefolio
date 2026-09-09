"""Tailored application links (#250) — admin minting + the public `/for/:slug`."""

import uuid
from datetime import UTC, datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tailored_links import (
    SLUG_SUFFIX_LENGTH,
    TailoredLinkIn,
    TailoredLinkPatch,
    _clean_highlights,
    generate_slug,
    slugify,
)
from app.config import settings
from app.models.cv_document import CvDocument
from app.models.tailored_link import TailoredLink

ADMIN_URL = f"{settings.api_prefix}/admin/tailored-links"
OPPORTUNITIES_URL = f"{settings.api_prefix}/admin/opportunities"
PUBLIC_URL = f"{settings.api_prefix}/for"


async def _opportunity(client: AsyncClient, **overrides) -> dict:
    body = {"company": "Acme GmbH", "role_title": "Staff Engineer"}
    body.update(overrides)
    resp = await client.post(OPPORTUNITIES_URL, json=body)
    assert resp.status_code == 201
    return resp.json()


async def _cv(db_session: AsyncSession, version: str = "acme-v1") -> CvDocument:
    doc = CvDocument(
        filename=f"{version}.pdf",
        data=b"%PDF-1.4 tailored",
        version=version,
        is_active=False,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def _link(client: AsyncClient, opportunity: dict, **overrides) -> dict:
    body = {"opportunity_id": opportunity["id"]}
    body.update(overrides)
    resp = await client.post(ADMIN_URL, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Acme GmbH", "acme-gmbh"),
        ("  Staff Engineer / Platform  ", "staff-engineer-platform"),
        ("Ünïcödé", "n-c-d"),
        ("!!!", ""),
    ],
)
def test_slugify(value, expected):
    assert slugify(value) == expected


def test_generate_slug_is_readable_and_unguessable():
    slug = generate_slug("Acme GmbH", "Staff Engineer")
    assert slug.startswith("acme-gmbh-staff-engineer-")
    assert len(slug.rsplit("-", 1)[1]) == SLUG_SUFFIX_LENGTH
    # The URL is the only secret this feature has: two mints never collide.
    assert generate_slug("Acme GmbH", "Staff Engineer") != slug


def test_generate_slug_without_any_usable_stem():
    """A company written entirely in a non-latin script still yields a slug —
    the random suffix alone, never an empty path segment."""
    slug = generate_slug("!!!", "???")
    assert len(slug) == SLUG_SUFFIX_LENGTH
    assert "-" not in slug


def test_clean_highlights_strips_dedupes_and_caps():
    assert _clean_highlights(None) == []
    assert _clean_highlights([" Angular ", "angular", "", "  ", "RxJS"]) == [
        "Angular",
        "RxJS",
    ]
    assert len(_clean_highlights([f"skill-{i}" for i in range(50)])) == 20


def test_is_live_treats_disabled_and_expired_alike():
    now = datetime.now(UTC)
    assert TailoredLink(enabled=True, expires_at=None).is_live(now) is True
    assert TailoredLink(enabled=False, expires_at=None).is_live(now) is False
    assert (
        TailoredLink(enabled=True, expires_at=now - timedelta(minutes=1)).is_live(now)
        is False
    )
    assert (
        TailoredLink(enabled=True, expires_at=now + timedelta(minutes=1)).is_live(now)
        is True
    )


# --------------------------------------------------------------------------
# Admin surface
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_surface_requires_auth(clean_client: AsyncClient):
    fake = str(uuid.uuid4())
    assert (await clean_client.get(ADMIN_URL)).status_code == 401
    assert (
        await clean_client.post(ADMIN_URL, json={"opportunity_id": fake})
    ).status_code == 401
    assert (
        await clean_client.patch(f"{ADMIN_URL}/{fake}", json={"enabled": False})
    ).status_code == 401
    assert (await clean_client.delete(f"{ADMIN_URL}/{fake}")).status_code == 401


@pytest.mark.asyncio
async def test_create_generates_slug_and_records_the_timeline(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity)

    assert link["slug"].startswith("acme-gmbh-staff-engineer-")
    assert link["path"] == f"/for/{link['slug']}"
    assert link["url"].endswith(link["path"])
    assert link["enabled"] is True
    assert link["visit_count"] == 0

    detail = (await client.get(f"{OPPORTUNITIES_URL}/{opportunity['id']}")).json()
    assert any(
        n["body"] == f"Tailored link created: /for/{link['slug']}"
        for n in detail["notes"]
    )


@pytest.mark.asyncio
async def test_create_with_custom_slug_note_highlights_and_variant(
    client: AsyncClient, db_session: AsyncSession
):
    opportunity = await _opportunity(client)
    cv = await _cv(db_session)
    link = await _link(
        client,
        opportunity,
        slug="acme-staff-eng",
        cv_document_id=str(cv.id),
        headline_note="  Hi Acme team — here is why I fit this role.  ",
        highlighted_skills=[" Angular ", "angular", "RxJS"],
        highlighted_projects=["Hirefolio"],
    )

    assert link["slug"] == "acme-staff-eng"
    assert link["headline_note"] == "Hi Acme team — here is why I fit this role."
    assert link["highlighted_skills"] == ["Angular", "RxJS"]
    assert link["cv_version"] == "acme-v1"
    assert link["cv_filename"] == "acme-v1.pdf"


@pytest.mark.asyncio
async def test_create_rejects_a_duplicate_slug(client: AsyncClient):
    opportunity = await _opportunity(client)
    await _link(client, opportunity, slug="acme-staff-eng")
    resp = await client.post(
        ADMIN_URL, json={"opportunity_id": opportunity["id"], "slug": "acme-staff-eng"}
    )
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "slug", ["Acme-Staff", "-acme", "acme-", "acme staff", "acme/staff", "acmé"]
)
@pytest.mark.asyncio
async def test_create_rejects_an_unusable_slug(client: AsyncClient, slug):
    opportunity = await _opportunity(client)
    resp = await client.post(
        ADMIN_URL, json={"opportunity_id": opportunity["id"], "slug": slug}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_unknown_opportunity_and_cv(
    client: AsyncClient, db_session: AsyncSession
):
    fake = str(uuid.uuid4())
    assert (
        await client.post(ADMIN_URL, json={"opportunity_id": fake})
    ).status_code == 404

    opportunity = await _opportunity(client)
    resp = await client.post(
        ADMIN_URL, json={"opportunity_id": opportunity["id"], "cv_document_id": fake}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_filters_by_opportunity(
    client: AsyncClient, db_session: AsyncSession
):
    first = await _opportunity(client)
    second = await _opportunity(client, company="Globex")
    cv = await _cv(db_session)
    a = await _link(client, first, cv_document_id=str(cv.id))
    b = await _link(client, second)

    everything = (await client.get(ADMIN_URL)).json()
    assert {row["id"] for row in everything} == {a["id"], b["id"]}
    # The CV label is resolved in ONE query for the whole page, not per row.
    assert [row["cv_version"] for row in everything if row["id"] == a["id"]] == [
        "acme-v1"
    ]

    filtered = (
        await client.get(ADMIN_URL, params={"opportunity_id": second["id"]})
    ).json()
    assert [row["id"] for row in filtered] == [b["id"]]


@pytest.mark.asyncio
async def test_patch_updates_every_field(client: AsyncClient, db_session: AsyncSession):
    opportunity = await _opportunity(client)
    cv = await _cv(db_session)
    link = await _link(client, opportunity, headline_note="first")

    expiry = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    updated = (
        await client.patch(
            f"{ADMIN_URL}/{link['id']}",
            json={
                "enabled": False,
                "cv_document_id": str(cv.id),
                "headline_note": "second",
                "highlighted_skills": ["Python"],
                "highlighted_projects": ["Hirefolio", "hirefolio"],
                "expires_at": expiry,
            },
        )
    ).json()

    assert updated["enabled"] is False
    assert updated["cv_version"] == "acme-v1"
    assert updated["headline_note"] == "second"
    assert updated["highlighted_skills"] == ["Python"]
    assert updated["highlighted_projects"] == ["Hirefolio"]
    assert updated["expires_at"] is not None

    # A patch that touches something else must KEEP the pinned variant label —
    # the admin panel re-renders from this response.
    kept = (
        await client.patch(f"{ADMIN_URL}/{link['id']}", json={"enabled": True})
    ).json()
    assert kept["cv_version"] == "acme-v1"
    assert kept["enabled"] is True

    cleared = (
        await client.patch(
            f"{ADMIN_URL}/{link['id']}",
            json={"clear_cv": True, "clear_expiry": True, "headline_note": "   "},
        )
    ).json()
    assert cleared["cv_document_id"] is None
    assert cleared["cv_version"] is None
    assert cleared["expires_at"] is None
    assert cleared["headline_note"] is None


@pytest.mark.asyncio
async def test_patch_rejects_unknown_link_and_unknown_cv(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity)
    fake = str(uuid.uuid4())

    assert (
        await client.patch(f"{ADMIN_URL}/{fake}", json={"enabled": False})
    ).status_code == 404
    assert (
        await client.patch(f"{ADMIN_URL}/{link['id']}", json={"cv_document_id": fake})
    ).status_code == 404


@pytest.mark.asyncio
async def test_delete_revokes_the_public_page(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity)

    assert (await client.get(f"{PUBLIC_URL}/{link['slug']}")).status_code == 200
    assert (await client.delete(f"{ADMIN_URL}/{link['id']}")).status_code == 204
    assert (await client.get(f"{PUBLIC_URL}/{link['slug']}")).status_code == 404
    assert (await client.delete(f"{ADMIN_URL}/{link['id']}")).status_code == 404


# --------------------------------------------------------------------------
# Public surface
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_view_is_open_and_leaks_no_owner_metrics(
    clean_client: AsyncClient, client: AsyncClient, db_session: AsyncSession
):
    opportunity = await _opportunity(client)
    cv = await _cv(db_session)
    link = await _link(
        client,
        opportunity,
        slug="acme-staff-eng",
        cv_document_id=str(cv.id),
        headline_note="Hi Acme team",
        highlighted_skills=["Angular"],
        highlighted_projects=["Hirefolio"],
    )

    # No auth header at all — the slug IS the access control.
    resp = await clean_client.get(f"{PUBLIC_URL}/{link['slug']}")
    assert resp.status_code == 200
    view = resp.json()
    assert view == {
        "slug": "acme-staff-eng",
        "company": "Acme GmbH",
        "role_title": "Staff Engineer",
        "headline_note": "Hi Acme team",
        "highlighted_skills": ["Angular"],
        "highlighted_projects": ["Hirefolio"],
        "cv_version": "acme-v1",
        "cv_download_path": f"{settings.api_prefix}/for/acme-staff-eng/cv",
    }
    # The recipient must not be able to read the owner's pipeline out of it.
    assert "visit_count" not in view
    assert "opportunity_id" not in view


@pytest.mark.asyncio
async def test_public_view_without_a_pinned_variant(client: AsyncClient):
    opportunity = await _opportunity(client)
    # Explicit nulls, the shape the admin form posts for its empty controls.
    link = await _link(client, opportunity, slug=None, headline_note=None)
    view = (await client.get(f"{PUBLIC_URL}/{link['slug']}")).json()
    assert view["cv_version"] is None
    assert view["cv_download_path"] is None


@pytest.mark.asyncio
async def test_unknown_disabled_and_expired_slugs_are_all_404(client: AsyncClient):
    assert (await client.get(f"{PUBLIC_URL}/nope")).status_code == 404

    opportunity = await _opportunity(client)
    disabled = await _link(client, opportunity, slug="disabled-link")
    await client.patch(f"{ADMIN_URL}/{disabled['id']}", json={"enabled": False})
    assert (await client.get(f"{PUBLIC_URL}/disabled-link")).status_code == 404

    expired = await _link(
        client,
        opportunity,
        slug="expired-link",
        expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    assert expired["expires_at"] is not None
    assert (await client.get(f"{PUBLIC_URL}/expired-link")).status_code == 404
    assert (await client.post(f"{PUBLIC_URL}/expired-link/visit")).status_code == 404
    assert (await client.get(f"{PUBLIC_URL}/expired-link/cv")).status_code == 404


@pytest.mark.asyncio
async def test_visits_land_on_the_opportunity_timeline(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity, slug="acme-staff-eng")

    assert (await client.post(f"{PUBLIC_URL}/acme-staff-eng/visit")).status_code == 204
    assert (await client.post(f"{PUBLIC_URL}/acme-staff-eng/visit")).status_code == 204

    rows = (
        await client.get(ADMIN_URL, params={"opportunity_id": opportunity["id"]})
    ).json()
    assert rows[0]["visit_count"] == 2
    assert rows[0]["last_visited_at"] is not None

    detail = (await client.get(f"{OPPORTUNITIES_URL}/{opportunity['id']}")).json()
    bodies = [n["body"] for n in detail["notes"]]
    assert "Tailored link /for/acme-staff-eng opened (visit #1)" in bodies
    assert "Tailored link /for/acme-staff-eng opened (visit #2)" in bodies
    assert link["visit_count"] == 0  # the mint response predates both visits


@pytest.mark.asyncio
async def test_tailored_cv_serves_the_pinned_variant_and_counts_it(
    client: AsyncClient, db_session: AsyncSession
):
    opportunity = await _opportunity(client)
    cv = await _cv(db_session, version="acme-v2")
    link = await _link(
        client, opportunity, slug="acme-staff-eng", cv_document_id=str(cv.id)
    )

    resp = await client.get(f"{PUBLIC_URL}/acme-staff-eng/cv")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert 'filename="acme-v2.pdf"' in resp.headers["content-disposition"]
    assert resp.content == b"%PDF-1.4 tailored"

    rows = (
        await client.get(ADMIN_URL, params={"opportunity_id": opportunity["id"]})
    ).json()
    assert rows[0]["cv_download_count"] == 1
    detail = (await client.get(f"{OPPORTUNITIES_URL}/{opportunity['id']}")).json()
    assert "Tailored link /for/acme-staff-eng CV downloaded (#1)" in [
        n["body"] for n in detail["notes"]
    ]
    assert link["cv_download_count"] == 0


@pytest.mark.asyncio
async def test_tailored_cv_404s_without_a_pinned_variant(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity)
    resp = await client.get(f"{PUBLIC_URL}/{link['slug']}/cv")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "CV_ERROR_UNAVAILABLE"


@pytest.mark.asyncio
async def test_the_default_portfolio_is_untouched_by_an_unused_feature(
    clean_client: AsyncClient,
):
    """Criterion 5: with no links minted, nothing about the public site moves."""
    config = await clean_client.get(f"{settings.api_prefix}/config/site")
    assert config.status_code == 200
    assert "tailored" not in config.text.lower()
    assert (await clean_client.get(f"{PUBLIC_URL}/anything")).status_code == 404


# --------------------------------------------------------------------------
# Expiry semantics (#323 review round 1, finding 1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The `<input type="date">` shape: "through the end of that day".
        ("2026-12-01", datetime(2026, 12, 1, 23, 59, 59, 999999, tzinfo=UTC)),
        # An explicit time is honoured, NOT rounded up to end-of-day.
        ("2026-12-01T00:00:00Z", datetime(2026, 12, 1, 0, 0, tzinfo=UTC)),
        ("2026-12-01T10:30:00Z", datetime(2026, 12, 1, 10, 30, tzinfo=UTC)),
        # A naive timestamp is read as UTC (the documented contract). Without
        # this, `expires_at > now` raises TypeError — a 500, not a 404.
        ("2026-12-01T10:30:00", datetime(2026, 12, 1, 10, 30, tzinfo=UTC)),
        # An explicit offset survives: Pydantic's smart `date | datetime` union
        # would have collapsed this to a bare date, dropping time AND offset.
        (
            "2026-12-01T00:00:00+02:00",
            datetime(2026, 12, 1, 0, 0, tzinfo=timezone(timedelta(hours=2))),
        ),
        (None, None),
    ],
)
def test_expiry_normalisation_resolves_every_input_shape(raw, expected):
    parsed = TailoredLinkIn(opportunity_id=uuid.uuid4(), expires_at=raw)
    assert parsed.expires_at == expected
    # The PATCH path shares the contract: editing an expiry must not
    # reintroduce the off-by-one that creating it fixed.
    assert TailoredLinkPatch(expires_at=raw).expires_at == expected
    if expected is not None:
        assert parsed.expires_at.tzinfo is not None


@pytest.mark.asyncio
async def test_a_link_expiring_today_is_live_today_and_dead_tomorrow(
    client: AsyncClient,
):
    """The boundary the off-by-one broke.

    The owner picks TODAY in the date field. Before the fix that resolved to
    midnight UTC, so the link was already expired at the instant it was minted
    — a silent 404 for a recruiter who had just been sent the URL, with nothing
    wrong-looking in the admin panel.
    """
    opportunity = await _opportunity(client)
    today = datetime.now(UTC).date()
    link = await _link(
        client, opportunity, slug="expires-today", expires_at=today.isoformat()
    )

    stored = datetime.fromisoformat(link["expires_at"])
    assert stored == datetime.combine(today, time.max, tzinfo=UTC)

    # Live right now, and for the whole of the chosen day.
    assert (await client.get(f"{PUBLIC_URL}/expires-today")).status_code == 200
    assert (await client.post(f"{PUBLIC_URL}/expires-today/visit")).status_code == 204

    model = TailoredLink(enabled=True, expires_at=stored)
    last_moment = datetime.combine(today, time.max, tzinfo=UTC)
    assert model.is_live(last_moment - timedelta(microseconds=1)) is True
    # ...and dead the moment the day ends.
    assert model.is_live(last_moment + timedelta(microseconds=1)) is False
    assert model.is_live(last_moment + timedelta(days=1)) is False


@pytest.mark.asyncio
async def test_patching_an_expiry_to_today_keeps_the_link_live(client: AsyncClient):
    opportunity = await _opportunity(client)
    link = await _link(client, opportunity, slug="patched-expiry")
    today = datetime.now(UTC).date()

    patched = await client.patch(
        f"{ADMIN_URL}/{link['id']}", json={"expires_at": today.isoformat()}
    )
    assert patched.status_code == 200
    assert datetime.fromisoformat(patched.json()["expires_at"]) == datetime.combine(
        today, time.max, tzinfo=UTC
    )
    assert (await client.get(f"{PUBLIC_URL}/patched-expiry")).status_code == 200


# --------------------------------------------------------------------------
# Rate limiting the public writes (#323 review round 1, finding 2)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visit_is_rate_limited_after_the_budget(client: AsyncClient, monkeypatch):
    """The slug is unauthenticated BY DESIGN and meant to be forwarded, so an
    unlimited `/visit` lets any recipient append rows to the owner's timeline
    without bound and inflate the signal AC4 exists to produce."""
    from app.api import tailored_links as module

    monkeypatch.setattr(module.visit_rate_limiter, "max_requests", 3)
    opportunity = await _opportunity(client)
    await _link(client, opportunity, slug="rate-limited")

    for _ in range(3):
        assert (
            await client.post(f"{PUBLIC_URL}/rate-limited/visit")
        ).status_code == 204
    blocked = await client.post(f"{PUBLIC_URL}/rate-limited/visit")
    assert blocked.status_code == 429

    # The rejected request wrote NOTHING: no counter bump, no timeline row.
    rows = (
        await client.get(ADMIN_URL, params={"opportunity_id": opportunity["id"]})
    ).json()
    assert rows[0]["visit_count"] == 3
    detail = (await client.get(f"{OPPORTUNITIES_URL}/{opportunity['id']}")).json()
    opened = [n for n in detail["notes"] if "opened" in n["body"]]
    assert len(opened) == 3


@pytest.mark.asyncio
async def test_tailored_cv_download_is_rate_limited(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    """The CV download writes a row too, so it shares the budget."""
    from app.api import tailored_links as module

    monkeypatch.setattr(module.visit_rate_limiter, "max_requests", 2)
    opportunity = await _opportunity(client)
    cv = await _cv(db_session)
    await _link(client, opportunity, slug="rate-limited-cv", cv_document_id=str(cv.id))

    for _ in range(2):
        assert (await client.get(f"{PUBLIC_URL}/rate-limited-cv/cv")).status_code == 200
    assert (await client.get(f"{PUBLIC_URL}/rate-limited-cv/cv")).status_code == 429


def test_the_visit_limiter_is_wired_to_its_settings(monkeypatch):
    """Pin the WIRING with sentinels — asserting against unmodified defaults
    would pass even if the factory read the wrong setting (§25)."""
    from app.api import tailored_links as module

    monkeypatch.setattr(settings, "tailored_visit_rate_limit_requests", 4321)
    monkeypatch.setattr(settings, "tailored_visit_rate_limit_window_seconds", 1234)
    built = module._build_visit_limiter()
    assert built.max_requests == 4321
    assert built.window_seconds == 1234


def test_the_read_path_is_deliberately_not_rate_limited():
    """`GET /for/{slug}` is fetched during SSR by the frontend container, so a
    per-IP budget there would key EVERY server-rendered visit to one bucket and
    throttle the whole site. Only the writes carry the limiter."""
    from app.api import tailored_links as module

    limited = {
        route.path
        for route in module.public_router.routes
        if any(
            dep.call is module._enforce_visit_rate_limit
            for dep in route.dependant.dependencies
        )
    }
    assert limited == {"/for/{slug}/visit", "/for/{slug}/cv"}
