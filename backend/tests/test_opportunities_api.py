"""Job-search pipeline tests (#247, phase 1)."""

import pytest
from httpx import AsyncClient

from app.config import settings

URL = f"{settings.api_prefix}/admin/opportunities"


async def _create(client: AsyncClient, **overrides):
    body = {
        "company": "Acme GmbH",
        "role_title": "Staff Engineer",
    }
    body.update(overrides)
    return await client.post(URL, json=body)


@pytest.mark.asyncio
async def test_requires_admin_auth(clean_client: AsyncClient):
    assert (await clean_client.get(URL)).status_code == 401
    assert (
        await clean_client.post(URL, json={"company": "A", "role_title": "B"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_create_and_get(client: AsyncClient):
    resp = await _create(
        client,
        recruiter_name="Rita",
        recruiter_email="rita@a.example",
        link="https://jobs.example/1",
        salary_note="100k",
        next_action="Prepare call",
        next_action_date="2026-09-10",
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["stage"] == "lead"
    assert created["next_action_date"] == "2026-09-10"

    detail = (await client.get(f"{URL}/{created['id']}")).json()
    assert detail["company"] == "Acme GmbH"
    assert detail["notes"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides,detail_part",
    [
        ({"stage": "bogus"}, "stage"),
        ({"source": "bogus"}, "source"),
        ({"company": ""}, None),
        ({"next_action_date": "not-a-date"}, "next_action_date"),
    ],
)
async def test_create_validation(client: AsyncClient, overrides, detail_part):
    resp = await _create(client, **overrides)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_filters_and_pagination(client: AsyncClient):
    for i in range(3):
        await _create(client, company=f"C{i}")
    first = (await client.get(URL)).json()
    assert first["total"] == 3

    listed = (await client.get(f"{URL}?stage=lead&page=2&page_size=1")).json()
    assert listed["pages"] == 3 and len(listed["items"]) == 1

    assert (await client.get(f"{URL}?stage=bogus")).status_code == 422


@pytest.mark.asyncio
async def test_stage_move_records_timeline_note(client: AsyncClient):
    created = (await _create(client)).json()
    moved = (
        await client.patch(f"{URL}/{created['id']}/stage", json={"stage": "screening"})
    ).json()
    assert moved["stage"] == "screening"
    assert any("lead → screening" in n["body"] for n in moved["notes"])

    # same-stage move is a no-op (no duplicate note)
    again = (
        await client.patch(f"{URL}/{created['id']}/stage", json={"stage": "screening"})
    ).json()
    assert len(again["notes"]) == len(moved["notes"])

    assert (
        await client.patch(f"{URL}/{created['id']}/stage", json={"stage": "bogus"})
    ).status_code == 422
    assert (
        await client.patch(
            f"{URL}/00000000-0000-0000-0000-000000000000/stage",
            json={"stage": "offer"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_notes_timeline(client: AsyncClient):
    created = (await _create(client)).json()
    with_note = (
        await client.post(
            f"{URL}/{created['id']}/notes", json={"body": "Call went well."}
        )
    ).json()
    assert with_note["notes"][0]["body"] == "Call went well."

    assert (
        await client.post(f"{URL}/{created['id']}/notes", json={"body": ""})
    ).status_code == 422
    assert (
        await client.post(
            f"{URL}/00000000-0000-0000-0000-000000000000/notes",
            json={"body": "x"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_promote_interaction(client: AsyncClient):
    # create an inbox interaction via the public form (#69)
    interaction = (
        await client.post(
            f"{settings.api_prefix}/interactions/contact",
            json={
                "name": "Rita Recruiter",
                "email": "rita@agency.example",
                "company": "Agency GmbH",
                "message": "Role at Acme for you",
            },
        )
    ).json()

    promoted = await client.post(
        f"{URL}/promote",
        json={"interaction_id": interaction["id"], "role_title": "Staff Engineer"},
    )
    assert promoted.status_code == 201
    opp = promoted.json()
    assert opp["company"] == "Agency GmbH"
    assert opp["role_title"] == "Staff Engineer"
    assert opp["recruiter_email"] == "rita@agency.example"
    assert "Role at Acme for you" in opp["notes"][0]["body"]
    assert opp["notes"][0]["interaction_id"] == interaction["id"]

    # the inbox item moved along the workflow
    listed = (
        await client.get(f"{settings.api_prefix}/admin/interactions?status=in_progress")
    ).json()
    assert listed["total"] == 1

    assert (
        await client.post(
            f"{URL}/promote",
            json={"interaction_id": "00000000-0000-0000-0000-000000000000"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_promote_keeps_non_new_interaction_status(client: AsyncClient):
    """Promoting an already-worked interaction must not regress its status."""
    interaction = (
        await client.post(
            f"{settings.api_prefix}/interactions/contact",
            json={
                "name": "R",
                "email": "r@x.example",
                "company": "C",
                "message": "hello",
            },
        )
    ).json()
    await client.patch(
        f"{settings.api_prefix}/admin/interactions/{interaction['id']}",
        json={"status": "contacted"},
    )
    resp = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    assert resp.status_code == 201
    listed = (
        await client.get(f"{settings.api_prefix}/admin/interactions?status=contacted")
    ).json()
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_promote_fills_unknowns(client: AsyncClient):
    interaction = (
        await client.post(
            f"{settings.api_prefix}/interactions/contact",
            json={
                "name": "Nameless",
                "email": "n@x.example",
                "company": None,
                "message": "hi there",
            },
        )
    ).json()
    opp = (
        await client.post(f"{URL}/promote", json={"interaction_id": interaction["id"]})
    ).json()
    assert opp["company"] == "Unknown company"
    assert opp["role_title"] == "Unknown role"
