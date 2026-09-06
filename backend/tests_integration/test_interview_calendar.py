"""Interview calendar through the composed stack (#247 phase 2 / #70).

The unit tests prove the handlers against an ASGI transport; this proves the
composed path a user actually exercises: create an opportunity → schedule an
interview → see it in the dashboard's `upcoming` window → download an `.ics`
that a calendar client can parse. Serialization, the real router (including the
`.ics` suffix route), the real DB (timestamptz round-trip) and the auth
boundary all participate here and in no other tier.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from conftest import API


def _unfold(document: str) -> list[str]:
    """Unfold (RFC 5545 §3.1) into content lines, the way a client does."""
    return [line for line in document.replace("\r\n ", "").split("\r\n") if line]


def _parse_ics(document: str) -> dict[str, str]:
    """Parse the single VEVENT's properties into NAME → value.

    BEGIN/END are skipped deliberately: they repeat (VCALENDAR then VEVENT), so
    a flat map would silently keep only the last one — assert the envelope
    against the unfolded lines instead.
    """
    properties: dict[str, str] = {}
    for line in _unfold(document):
        name, _, value = line.partition(":")
        name = name.split(";")[0]
        if name in ("BEGIN", "END"):
            continue
        properties[name] = value
    return properties


def test_schedule_appears_in_upcoming_and_exports_a_parsable_ics(
    client: httpx.Client, admin_headers: dict[str, str]
):
    marker = f"iv-{uuid.uuid4().hex[:12]}"
    start = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)

    opportunity = client.post(
        f"{API}/admin/opportunities",
        json={"company": f"Calendar GmbH {marker}", "role_title": "Staff Engineer"},
        headers=admin_headers,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["id"]

    scheduled = client.post(
        f"{API}/admin/opportunities/{opportunity_id}/interviews",
        json={
            "scheduled_at": start.isoformat(),
            "duration_minutes": 60,
            "kind": "video",
            "location_or_link": "https://meet.example/integration",
            "interviewer": "Rita Recruiter",
        },
        headers=admin_headers,
    )
    assert scheduled.status_code == 201, scheduled.text
    interview_id = scheduled.json()["id"]

    # Scheduling moved the card along the pipeline (composed side effect).
    board_card = client.get(
        f"{API}/admin/opportunities/{opportunity_id}", headers=admin_headers
    )
    assert board_card.json()["stage"] == "interviewing"

    upcoming = client.get(f"{API}/admin/interviews/upcoming", headers=admin_headers)
    assert upcoming.status_code == 200, upcoming.text
    rows = [row for row in upcoming.json() if row["id"] == interview_id]
    assert len(rows) == 1, "the new interview must be inside the 14-day window"
    assert rows[0]["company"] == f"Calendar GmbH {marker}"
    assert rows[0]["role_title"] == "Staff Engineer"

    export = client.get(
        f"{API}/admin/interviews/{interview_id}.ics", headers=admin_headers
    )
    assert export.status_code == 200, export.text
    assert export.headers["content-type"].startswith("text/calendar")
    assert "attachment" in export.headers["content-disposition"]

    lines = _unfold(export.text)
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    assert "BEGIN:VEVENT" in lines and "END:VEVENT" in lines

    properties = _parse_ics(export.text)
    assert properties["VERSION"] == "2.0"
    assert properties["STATUS"] == "CONFIRMED"
    assert properties["UID"].startswith(interview_id)
    assert properties["LOCATION"] == "https://meet.example/integration"
    # The instant survived the timestamptz round trip through the real DB.
    assert properties["DTSTART"] == start.strftime("%Y%m%dT%H%M%SZ")
    assert properties["DTEND"] == (start + timedelta(minutes=60)).strftime(
        "%Y%m%dT%H%M%SZ"
    )


def test_cancelled_interview_leaves_the_upcoming_window(
    client: httpx.Client, admin_headers: dict[str, str]
):
    """Cancel through the real stack: the dashboard window drops the slot and
    the export flips to STATUS:CANCELLED so a calendar can retract the event."""
    marker = f"cancel-{uuid.uuid4().hex[:12]}"
    start = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0)

    opportunity_id = client.post(
        f"{API}/admin/opportunities",
        json={"company": f"Cancel GmbH {marker}", "role_title": "Principal"},
        headers=admin_headers,
    ).json()["id"]
    interview_id = client.post(
        f"{API}/admin/opportunities/{opportunity_id}/interviews",
        json={"scheduled_at": start.isoformat(), "kind": "onsite"},
        headers=admin_headers,
    ).json()["id"]

    patched = client.patch(
        f"{API}/admin/interviews/{interview_id}",
        json={"outcome": "cancelled"},
        headers=admin_headers,
    )
    assert patched.status_code == 200, patched.text

    upcoming = client.get(f"{API}/admin/interviews/upcoming", headers=admin_headers)
    assert [row for row in upcoming.json() if row["id"] == interview_id] == []

    export = client.get(
        f"{API}/admin/interviews/{interview_id}.ics", headers=admin_headers
    )
    assert _parse_ics(export.text)["STATUS"] == "CANCELLED"


def test_interview_surfaces_reject_anonymous_callers(client: httpx.Client):
    """Owner-private data: nothing about the schedule is readable unauthenticated
    (#247 acceptance criterion "nothing leaks into public endpoints")."""
    fake = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"{API}/admin/interviews/upcoming").status_code == 401
    assert client.get(f"{API}/admin/interviews/{fake}.ics").status_code == 401
    assert (
        client.post(
            f"{API}/admin/opportunities/{fake}/interviews",
            json={"scheduled_at": "2026-10-01T09:00:00+00:00"},
        ).status_code
        == 401
    )
