"""Interview calendar API tests (#70 / #247 phase 2)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.opportunity import Opportunity

OPPS = f"{settings.api_prefix}/admin/opportunities"
IVS = f"{settings.api_prefix}/admin/interviews"

FAKE_ID = "00000000-0000-0000-0000-000000000000"


def _in(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def _opportunity(client: AsyncClient, **overrides) -> dict:
    body = {"company": "Acme GmbH", "role_title": "Staff Engineer"}
    body.update(overrides)
    resp = await client.post(OPPS, json=body)
    assert resp.status_code == 201
    return resp.json()


async def _schedule(client: AsyncClient, opportunity_id: str, **overrides):
    body = {"scheduled_at": _in(24), "duration_minutes": 45, "kind": "video"}
    body.update(overrides)
    return await client.post(f"{OPPS}/{opportunity_id}/interviews", json=body)


@pytest.mark.asyncio
async def test_every_interview_surface_requires_admin_auth(clean_client: AsyncClient):
    assert (
        await clean_client.post(f"{OPPS}/{FAKE_ID}/interviews", json={})
    ).status_code == 401
    assert (await clean_client.get(f"{OPPS}/{FAKE_ID}/interviews")).status_code == 401
    assert (await clean_client.get(f"{IVS}/upcoming")).status_code == 401
    assert (await clean_client.get(f"{IVS}/{FAKE_ID}")).status_code == 401
    assert (await clean_client.get(f"{IVS}/{FAKE_ID}.ics")).status_code == 401
    assert (
        await clean_client.patch(f"{IVS}/{FAKE_ID}", json={"outcome": "passed"})
    ).status_code == 401
    assert (await clean_client.delete(f"{IVS}/{FAKE_ID}")).status_code == 401


@pytest.mark.asyncio
async def test_schedule_normalizes_the_instant_to_utc(client: AsyncClient):
    opp = await _opportunity(client)
    resp = await _schedule(
        client,
        opp["id"],
        scheduled_at="2026-09-10T16:30:00+02:00",
        location_or_link="https://meet.example/x",
        interviewer="Rita",
        notes="Bring the system-design deck",
    )
    assert resp.status_code == 201
    created = resp.json()
    # 16:30+02:00 is 14:30 UTC — one instant, not a string.
    assert created["scheduled_at"].startswith("2026-09-10T14:30:00")
    assert created["scheduled_at"].endswith("+00:00")
    assert created["outcome"] == "pending"
    assert created["duration_minutes"] == 45
    assert created["interviewer"] == "Rita"

    # The timeline note is written from the parsed value, not from the DB
    # round-trip: it is where a missing UTC conversion would leak "+02:00".
    bodies = [
        n["body"] for n in (await client.get(f"{OPPS}/{opp['id']}")).json()["notes"]
    ]
    assert any(
        "Interview scheduled: video on 2026-09-10T14:30:00+00:00" in b for b in bodies
    )


@pytest.mark.asyncio
async def test_schedule_accepts_a_naive_timestamp_as_utc(client: AsyncClient):
    opp = await _opportunity(client)
    created = (
        await _schedule(client, opp["id"], scheduled_at="2026-09-10T14:30:00")
    ).json()
    assert created["scheduled_at"].startswith("2026-09-10T14:30:00")
    assert created["scheduled_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_scheduling_advances_the_stage_and_writes_the_timeline(
    client: AsyncClient,
):
    opp = await _opportunity(client)  # stage: lead
    await _schedule(client, opp["id"])

    detail = (await client.get(f"{OPPS}/{opp['id']}")).json()
    assert detail["stage"] == "interviewing"
    bodies = [n["body"] for n in detail["notes"]]
    assert any("Interview scheduled: video" in b for b in bodies)
    assert any("Stage: lead → interviewing (interview scheduled)" in b for b in bodies)


@pytest.mark.asyncio
@pytest.mark.parametrize("later_stage", ["offer", "closed_won"])
async def test_scheduling_never_regresses_a_later_stage(
    client: AsyncClient, later_stage: str
):
    """Booking a follow-up round on a card that already reached offer/closed
    must not drag it back to `interviewing` (the promote handler's rule)."""
    opp = await _opportunity(client)
    await client.patch(f"{OPPS}/{opp['id']}/stage", json={"stage": later_stage})

    await _schedule(client, opp["id"])

    detail = (await client.get(f"{OPPS}/{opp['id']}")).json()
    assert detail["stage"] == later_stage
    assert not any("(interview scheduled)" in n["body"] for n in detail["notes"])


@pytest.mark.asyncio
async def test_scheduling_an_already_interviewing_card_keeps_its_stage(
    client: AsyncClient,
):
    opp = await _opportunity(client, stage="interviewing")
    await _schedule(client, opp["id"])
    detail = (await client.get(f"{OPPS}/{opp['id']}")).json()
    assert detail["stage"] == "interviewing"
    assert not any("(interview scheduled)" in n["body"] for n in detail["notes"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"duration_minutes": 5},
        {"duration_minutes": 1440},
        {"kind": "phone"},
        {"kind": "other"},
        {"notes": "n" * 20_000},
    ],
)
async def test_schedule_accepts_boundaries(client: AsyncClient, overrides):
    """The ACCEPT side of every bound the schema states. Only the reject side
    was covered, so a bound tightened by accident would not have failed a test
    (#289 review round 1)."""
    opp = await _opportunity(client)
    assert (await _schedule(client, opp["id"], **overrides)).status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "carrier-pigeon"},
        {"scheduled_at": "next tuesday"},
        {"scheduled_at": "   "},
        {"scheduled_at": None},
        {"duration_minutes": 0},
        {"duration_minutes": 2000},
        {"location_or_link": "x" * 1001},
        {"interviewer": "y" * 201},
        # Near datetime.max the offset shift raises OverflowError, not
        # ValueError, so the parser let it escape as an unhandled 500 (#289
        # review round 1).
        {"scheduled_at": "9999-12-31T23:59:59-14:00"},
        # ...and this one SURVIVED the shift and was accepted with 201, leaving
        # a row whose .ics export raised on every request, forever. The parser
        # now rejects any instant whose DTEND would not be representable at the
        # maximum duration the schema allows.
        {"scheduled_at": "9999-12-31T23:00:00+00:00"},
    ],
)
async def test_schedule_validation(client: AsyncClient, overrides):
    """Whitespace-only pins the strip-then-validate contract: padding must not
    satisfy a required field."""
    opp = await _opportunity(client)
    assert (await _schedule(client, opp["id"], **overrides)).status_code == 422


@pytest.mark.asyncio
async def test_schedule_on_unknown_opportunity_is_404(client: AsyncClient):
    assert (await _schedule(client, FAKE_ID)).status_code == 404
    assert (await client.get(f"{OPPS}/{FAKE_ID}/interviews")).status_code == 404


@pytest.mark.asyncio
async def test_list_returns_the_opportunitys_interviews_soonest_first(
    client: AsyncClient,
):
    opp = await _opportunity(client)
    later = (await _schedule(client, opp["id"], scheduled_at=_in(72))).json()
    sooner = (await _schedule(client, opp["id"], scheduled_at=_in(2))).json()

    listed = (await client.get(f"{OPPS}/{opp['id']}/interviews")).json()
    assert [iv["id"] for iv in listed] == [sooner["id"], later["id"]]


@pytest.mark.asyncio
async def test_reschedule_and_outcome_are_recorded_on_the_timeline(
    client: AsyncClient,
):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"])).json()

    moved = await client.patch(
        f"{IVS}/{interview['id']}",
        json={"scheduled_at": "2026-10-01T11:00:00+02:00", "duration_minutes": 90},
    )
    assert moved.status_code == 200
    assert moved.json()["scheduled_at"].startswith("2026-10-01T09:00:00")
    assert moved.json()["duration_minutes"] == 90

    scored = await client.patch(f"{IVS}/{interview['id']}", json={"outcome": "passed"})
    assert scored.json()["outcome"] == "passed"

    bodies = [
        n["body"] for n in (await client.get(f"{OPPS}/{opp['id']}")).json()["notes"]
    ]
    assert any(
        "Interview rescheduled:" in b and "2026-10-01T09:00:00+00:00" in b
        for b in bodies
    )
    assert any("Interview outcome: pending → passed" in b for b in bodies)


@pytest.mark.asyncio
async def test_patch_without_real_changes_writes_no_timeline_noise(
    client: AsyncClient,
):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"])).json()
    before = len((await client.get(f"{OPPS}/{opp['id']}")).json()["notes"])

    resp = await client.patch(
        f"{IVS}/{interview['id']}",
        json={
            "scheduled_at": interview["scheduled_at"],
            "outcome": "pending",
            "interviewer": None,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["interviewer"] is None  # explicit null clears an optional
    after = (await client.get(f"{OPPS}/{opp['id']}")).json()["notes"]
    assert len(after) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"kind": "smoke-signal"},
        {"outcome": "brilliant"},
        {"kind": None},
        {"outcome": None},
        {"scheduled_at": None},
        {"duration_minutes": None},
        {"scheduled_at": "whenever"},
        {"duration_minutes": 4},
        # Non-string input is refused by the schema, before the ISO parser —
        # which is why the parser carries no isinstance branch.
        {"scheduled_at": 5},
        {"scheduled_at": ["2026-10-01T09:00:00+00:00"]},
    ],
)
async def test_patch_validation(client: AsyncClient, patch):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"])).json()
    assert (
        await client.patch(f"{IVS}/{interview['id']}", json=patch)
    ).status_code == 422


@pytest.mark.asyncio
async def test_patch_unknown_interview_is_404(client: AsyncClient):
    assert (
        await client.patch(f"{IVS}/{FAKE_ID}", json={"outcome": "passed"})
    ).status_code == 404


@pytest.mark.asyncio
async def test_delete_removes_the_slot_but_keeps_the_history(client: AsyncClient):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"])).json()

    assert (await client.delete(f"{IVS}/{interview['id']}")).status_code == 204
    assert (await client.get(f"{OPPS}/{opp['id']}/interviews")).json() == []
    bodies = [
        n["body"] for n in (await client.get(f"{OPPS}/{opp['id']}")).json()["notes"]
    ]
    assert any("Interview removed: video" in b and "pending" in b for b in bodies)

    assert (await client.delete(f"{IVS}/{interview['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_upcoming_lists_the_window_soonest_first_with_company_context(
    client: AsyncClient,
):
    acme = await _opportunity(client, company="Acme GmbH", role_title="Staff Engineer")
    globex = await _opportunity(client, company="Globex", role_title="Principal")

    soon = (await _schedule(client, globex["id"], scheduled_at=_in(3))).json()
    later = (await _schedule(client, acme["id"], scheduled_at=_in(48))).json()
    await _schedule(client, acme["id"], scheduled_at=_in(-5))  # already happened
    await _schedule(client, acme["id"], scheduled_at=_in(24 * 30))  # beyond the window

    rows = (await client.get(f"{IVS}/upcoming")).json()
    assert [r["id"] for r in rows] == [soon["id"], later["id"]]
    assert rows[0]["company"] == "Globex"
    assert rows[0]["role_title"] == "Principal"
    assert rows[0]["stage"] == "interviewing"


@pytest.mark.asyncio
async def test_scheduling_leaves_an_unrecognised_stage_alone(
    client: AsyncClient, db_session
):
    """Stage drift is a DATA problem, not a client error. `.index()` on a stage
    outside OPPORTUNITY_STAGES raised ValueError -> 500 (#289 review round 1);
    the row is now left untouched, because silently rewriting a stage the code
    does not recognise would be worse than leaving it."""
    opp = await _opportunity(client)
    row = await db_session.get(Opportunity, uuid.UUID(opp["id"]))
    row.stage = "archived_by_an_older_release"
    await db_session.commit()

    assert (await _schedule(client, opp["id"])).status_code == 201

    await db_session.refresh(row)
    assert row.stage == "archived_by_an_older_release"


@pytest.mark.asyncio
async def test_upcoming_keeps_an_interview_that_is_still_running(client: AsyncClient):
    """A round that has STARTED but not ended is the most relevant row on the
    dashboard, and `scheduled_at >= now` dropped it the moment it began (#289
    review round 1). The one that already ended must still be excluded — the
    predicate is per-row end time, not a blanket lookback."""
    opp = await _opportunity(client)
    running = (
        await _schedule(client, opp["id"], scheduled_at=_in(-0.5), duration_minutes=60)
    ).json()
    await _schedule(client, opp["id"], scheduled_at=_in(-2), duration_minutes=30)

    rows = (await client.get(f"{IVS}/upcoming")).json()
    assert [r["id"] for r in rows] == [running["id"]]


@pytest.mark.asyncio
async def test_upcoming_window_is_configurable_and_bounded(client: AsyncClient):
    opp = await _opportunity(client)
    await _schedule(client, opp["id"], scheduled_at=_in(24 * 20))

    assert (await client.get(f"{IVS}/upcoming")).json() == []  # default 14 days
    assert len((await client.get(f"{IVS}/upcoming?days=30")).json()) == 1
    assert (await client.get(f"{IVS}/upcoming?days=0")).status_code == 422
    assert (await client.get(f"{IVS}/upcoming?days=400")).status_code == 422


@pytest.mark.asyncio
async def test_upcoming_excludes_cancelled_slots(client: AsyncClient):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"], scheduled_at=_in(5))).json()
    assert len((await client.get(f"{IVS}/upcoming")).json()) == 1

    await client.patch(f"{IVS}/{interview['id']}", json={"outcome": "cancelled"})
    assert (await client.get(f"{IVS}/upcoming")).json() == []


@pytest.mark.asyncio
async def test_ics_export_is_a_downloadable_rfc5545_event(
    client: AsyncClient, monkeypatch
):
    # Distinct pinned value, not the default (§25): the UID domain must come
    # from the configured site, not a hardcoded literal.
    monkeypatch.setattr(settings, "site_url", "https://pinned-host.example/base")
    opp = await _opportunity(
        client, company="Acme, Inc.", link="https://jobs.example/1"
    )
    interview = (
        await _schedule(
            client,
            opp["id"],
            scheduled_at="2026-09-10T16:30:00+02:00",
            duration_minutes=45,
            location_or_link="https://meet.example/x",
            interviewer="Rita",
            notes="Bring the deck",
        )
    ).json()

    resp = await client.get(f"{IVS}/{interview['id']}.ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert (
        f'filename="interview-{interview["id"]}.ics"'
        in (resp.headers["content-disposition"])
    )
    document = resp.text.replace("\r\n ", "")
    assert f"UID:{interview['id']}@pinned-host.example" in document
    assert "DTSTART:20260910T143000Z" in document  # normalized to UTC
    assert "DTEND:20260910T151500Z" in document  # + 45 minutes
    assert "STATUS:CONFIRMED" in document
    assert "SUMMARY:Interview: Acme\\, Inc. — Staff Engineer" in document
    assert "LOCATION:https://meet.example/x" in document
    assert "Interviewer: Rita" in document
    assert "Job posting: https://jobs.example/1" in document


@pytest.mark.asyncio
async def test_ics_export_marks_a_cancelled_slot_and_survives_a_blank_site_url(
    client: AsyncClient, monkeypatch
):
    """An unset site_url must still yield a syntactically valid UID."""
    monkeypatch.setattr(settings, "site_url", "")
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"], kind="onsite")).json()
    await client.patch(f"{IVS}/{interview['id']}", json={"outcome": "cancelled"})

    document = (await client.get(f"{IVS}/{interview['id']}.ics")).text
    assert f"UID:{interview['id']}@hirefolio" in document
    assert "STATUS:CANCELLED" in document


@pytest.mark.asyncio
async def test_get_one_interview(client: AsyncClient):
    opp = await _opportunity(client)
    interview = (await _schedule(client, opp["id"])).json()
    fetched = await client.get(f"{IVS}/{interview['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == interview["id"]
    assert (await client.get(f"{IVS}/{FAKE_ID}")).status_code == 404


@pytest.mark.asyncio
async def test_ics_export_of_an_unknown_interview_is_404(client: AsyncClient):
    assert (await client.get(f"{IVS}/{FAKE_ID}.ics")).status_code == 404
    # A non-UUID id is a 422 from the path validator, never a 500.
    assert (await client.get(f"{IVS}/not-a-uuid.ics")).status_code == 422


@pytest.mark.asyncio
async def test_upcoming_is_not_swallowed_by_the_id_route(client: AsyncClient):
    """Route-order regression: '/upcoming' is declared before '/{interview_id}',
    so it must not be parsed as a UUID path parameter."""
    resp = await client.get(f"{IVS}/upcoming")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_deleting_the_opportunity_cascades_to_its_interviews(
    client: AsyncClient, db_session
):
    """The FK is ON DELETE CASCADE: an opportunity thread takes its schedule
    with it (there is no orphaned-slot state to clean up later)."""
    from sqlalchemy import delete, func, select

    from app.models.interview import Interview
    from app.models.opportunity import Opportunity

    opp = await _opportunity(client)
    await _schedule(client, opp["id"])

    # A core DELETE (not an ORM cascade) so this pins the DATABASE-level
    # ON DELETE CASCADE, which is what a real `DELETE FROM opportunities` hits.
    await db_session.execute(
        delete(Opportunity).where(Opportunity.id == uuid.UUID(opp["id"]))
    )
    await db_session.commit()

    remaining = (
        await db_session.execute(select(func.count(Interview.id)))
    ).scalar_one()
    assert remaining == 0
