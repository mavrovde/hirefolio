"""Job-search pipeline tests (#247, phase 1)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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
    fake = str(uuid.uuid4())
    assert (await clean_client.get(URL)).status_code == 401
    assert (
        await clean_client.post(URL, json={"company": "A", "role_title": "B"})
    ).status_code == 401
    # Every admin surface, not just the collection (#274 review AC6 gap):
    assert (
        await clean_client.post(f"{URL}/promote", json={"interaction_id": fake})
    ).status_code == 401
    assert (
        await clean_client.post(f"{URL}/{fake}/notes", json={"body": "x"})
    ).status_code == 401
    assert (
        await clean_client.patch(f"{URL}/{fake}/stage", json={"stage": "lead"})
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
    "overrides",
    [
        {"stage": "bogus"},
        {"source": "bogus"},
        {"company": ""},
        {"company": "   "},
        {"role_title": "\t\t"},
        {"company": "x" * 201},
        {"next_action_date": "not-a-date"},
    ],
)
async def test_create_validation(client: AsyncClient, overrides):
    """Whitespace-only cases pin the strip-then-validate contract (#274 review
    major 3): padding must not create a blank, permanent card — phase 1 has no
    DELETE to undo one."""
    resp = await _create(client, **overrides)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_note_rejects_whitespace_only_body(client: AsyncClient):
    created = (await _create(client)).json()
    resp = await client.post(f"{URL}/{created['id']}/notes", json={"body": " \n "})
    assert resp.status_code == 422


async def _seed_interaction(client: AsyncClient, source: str = "contact_form"):
    """Create an interaction of the given source (contact_form via the public
    endpoint; other sources are written directly — they have their own flows)."""
    resp = await client.post(
        f"{settings.api_prefix}/interactions/contact",
        json={
            "name": "Rita Recruiter",
            "email": "rita@agency.example",
            "company": "Agency GmbH",
            "message": "Role at Acme for you",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_promote_survives_two_concurrent_requests(
    client: AsyncClient, db_session
):
    """#279 under CONCURRENCY — the property the sequential test cannot reach.

    `get_db` yields a FRESH session per request, so two clicks arriving together
    both pass an application-level "does a card exist?" check and both insert;
    a review reproduced that with two sessions and a barrier and got two
    permanent cards (the router has no DELETE). This test drives the same race
    through two independent sessions and asserts the DB-level UNIQUE on
    `promoted_from_interaction_id` collapses it to one card.

    It fails against the pre-promote0005 code: without the constraint both
    inserts commit.
    """
    import asyncio

    from sqlalchemy.exc import IntegrityError

    from app.models.opportunity import Opportunity
    from conftest import get_test_async_session

    interaction = await _seed_interaction(client)
    interaction_id = uuid.UUID(interaction["id"])
    sessionmaker = get_test_async_session()
    barrier = asyncio.Barrier(2)

    async def racing_promote() -> str:
        async with sessionmaker() as session:
            # Both racers read "no existing card"...
            found = (
                (
                    await session.execute(
                        select(Opportunity).where(
                            Opportunity.promoted_from_interaction_id == interaction_id
                        )
                    )
                )
                .scalars()
                .first()
            )
            await barrier.wait()  # ...then both try to insert.
            if found is not None:
                return "existing"
            session.add(
                Opportunity(
                    company="Race GmbH",
                    role_title="Race Engineer",
                    stage="lead",
                    source="recruiter_outreach",
                    promoted_from_interaction_id=interaction_id,
                )
            )
            try:
                await session.commit()
                return "created"
            except IntegrityError:
                await session.rollback()
                return "collapsed"

    outcomes = await asyncio.gather(racing_promote(), racing_promote())

    rows = (
        (
            await db_session.execute(
                select(Opportunity).where(
                    Opportunity.promoted_from_interaction_id == interaction_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"the race created {len(rows)} cards; outcomes={outcomes}"
    assert "created" in outcomes
    # The loser must have been rejected by the constraint, not silently duplicated.
    assert "collapsed" in outcomes or outcomes.count("created") == 1


@pytest.mark.asyncio
async def test_promote_recovers_when_it_loses_the_race(
    client: AsyncClient, db_session, monkeypatch
):
    """The API's own recovery path: the pre-insert lookup misses (as it does
    for the loser of a real race), the UNIQUE rejects the insert, and the
    handler must return the WINNER's card instead of 500-ing.

    Simulated by blinding the first lookup — the same state the loser sees
    between its check and its commit.
    """
    from app.api import opportunities as module

    interaction = await _seed_interaction(client)
    winner = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    assert winner.status_code == 201

    real_find = module._find_promoted
    calls = {"n": 0}

    async def blind_once(db, interaction_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # the loser's stale read
        return await real_find(db, interaction_id)

    monkeypatch.setattr(module, "_find_promoted", blind_once)

    loser = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    assert loser.status_code == 201, loser.text
    assert loser.json()["id"] == winner.json()["id"]
    assert calls["n"] == 2  # blinded lookup, then the recovery lookup

    from app.models.opportunity import Opportunity

    rows = (
        (
            await db_session.execute(
                select(Opportunity).where(
                    Opportunity.promoted_from_interaction_id
                    == uuid.UUID(interaction["id"])
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_promote_ignores_a_forged_note_link(client: AsyncClient):
    """The idempotency key is the opportunity's OWN column, not a note's
    interaction_id — notes are admin-writable, so a key derived from them could
    be forged to make promote return an unrelated card (review finding)."""
    unrelated = (await _create(client, company="Unrelated GmbH")).json()
    interaction = await _seed_interaction(client)

    # An admin links a note on the unrelated card to this interaction.
    linked = await client.post(
        f"{URL}/{unrelated['id']}/notes",
        json={"body": "linking note", "interaction_id": interaction["id"]},
    )
    assert linked.status_code == 201

    promoted = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    assert promoted.status_code == 201
    # A NEW card, not the forged one.
    assert promoted.json()["id"] != unrelated["id"]
    assert promoted.json()["company"] == "Agency GmbH"


@pytest.mark.asyncio
async def test_promote_is_idempotent_per_interaction(client: AsyncClient, db_session):
    """#279: a double-click (or a retry) must not mint a second permanent card —
    phase 1 has no DELETE to undo one. The second promote returns the SAME card."""
    interaction = await _seed_interaction(client)
    first = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    second = await client.post(
        f"{URL}/promote", json={"interaction_id": interaction["id"]}
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    from app.models.opportunity import Opportunity

    rows = (await db_session.execute(select(Opportunity))).scalars().all()
    assert len(rows) == 1
    # The repeat must not duplicate the timeline note either.
    assert len(second.json()["notes"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "interaction_source,expected_source",
    [
        ("contact_form", "recruiter_outreach"),
        ("cv_request", "discovery"),
        ("booking", "discovery"),
    ],
)
async def test_promote_maps_the_interaction_source(
    client: AsyncClient, db_session, interaction_source, expected_source
):
    """#278: the card's source derives from where the interaction CAME FROM —
    hardcoding recruiter_outreach mislabelled every cv_request and booking."""
    from app.models.interaction import Interaction

    row = Interaction(
        source=interaction_source,
        status="new",
        name="Rita Recruiter",
        email="rita@agency.example",
        company="Agency GmbH",
        message="Role at Acme for you",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    resp = await client.post(f"{URL}/promote", json={"interaction_id": str(row.id)})
    assert resp.status_code == 201
    assert resp.json()["source"] == expected_source


@pytest.mark.asyncio
async def test_promote_unknown_source_falls_back_safely(
    client: AsyncClient, db_session
):
    """An interaction source added later (messengers #263, voice #264) must not
    500 the promote path before its mapping lands — it degrades to the default."""
    from app.models.interaction import Interaction

    row = Interaction(
        source="contact_form",
        status="new",
        name="Rita",
        email="r@x.example",
        company="C",
        message="hello there",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    # Simulate a source with no mapping entry yet.
    row.source = "telegram"
    await db_session.commit()

    resp = await client.post(f"{URL}/promote", json={"interaction_id": str(row.id)})
    assert resp.status_code == 201
    assert resp.json()["source"] == "recruiter_outreach"


@pytest.mark.asyncio
async def test_promote_whitespace_company_falls_back_to_interaction(
    client: AsyncClient,
):
    """A whitespace-only override normalizes to None, so the promoted card
    keeps the interaction's own company instead of a blank string."""
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
    resp = await client.post(
        f"{URL}/promote",
        json={"interaction_id": interaction["id"], "company": "   "},
    )
    assert resp.status_code == 201
    assert resp.json()["company"] == "Agency GmbH"


@pytest.mark.asyncio
async def test_promote_explicit_null_overrides_ride_the_normalizer(
    client: AsyncClient,
):
    """Explicit null must ride the normalizer's non-str fall-through unchanged
    (the #258 lesson: omitting the key skips validators on defaults entirely).
    A FRESH interaction on purpose — promote is idempotent now (#279), so a
    second call on the same interaction returns the first card and would never
    exercise the override path."""
    interaction = await _seed_interaction(client)
    resp = await client.post(
        f"{URL}/promote",
        json={
            "interaction_id": interaction["id"],
            "company": None,
            "role_title": "Staff Engineer",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["company"] == "Agency GmbH"
    assert resp.json()["role_title"] == "Staff Engineer"


@pytest.mark.asyncio
async def test_promote_overrides_apply_only_on_first_promotion(client: AsyncClient):
    """Documented consequence of idempotency (#279): overrides passed to a
    REPEAT promote are ignored — the existing card is returned untouched. A
    caller that wants to change a card edits it, it does not re-promote."""
    interaction = await _seed_interaction(client)
    first = await client.post(
        f"{URL}/promote",
        json={"interaction_id": interaction["id"], "role_title": "Staff Engineer"},
    )
    second = await client.post(
        f"{URL}/promote",
        json={"interaction_id": interaction["id"], "role_title": "Principal Engineer"},
    )
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["role_title"] == "Staff Engineer"


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
                "name": "Rita R.",
                "email": "r@x.example",
                "company": "C",
                "message": "hello there",
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
