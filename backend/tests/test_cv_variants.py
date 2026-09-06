"""CV variants on opportunities (#247 criterion 4).

The variant machinery itself (multiple named versions, one active) predates
this feature — what these tests pin is the NEW claim set: an opportunity
records which variant was sent and when, the record survives on the timeline,
and — the invariant that actually matters — recording a send NEVER touches
which CV the public flow serves.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.cv_document import CvDocument

OPPS = f"{settings.api_prefix}/admin/opportunities"

FAKE_ID = "00000000-0000-0000-0000-000000000000"


async def _opportunity(client: AsyncClient) -> dict:
    r = await client.post(
        OPPS, json={"company": "Acme GmbH", "role_title": "Staff Engineer"}
    )
    assert r.status_code == 201
    return r.json()


async def _cv(db_session, version: str, active: bool = False) -> CvDocument:
    doc = CvDocument(
        filename=f"cv-{version}.pdf",
        data=b"%PDF-1.4 fake",
        version=version,
        is_active=active,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_recording_a_sent_variant_sets_fields_and_timeline(
    client: AsyncClient, db_session
):
    opp = await _opportunity(client)
    doc = await _cv(db_session, "backend-focus")

    r = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(doc.id)}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["sent_cv_id"] == str(doc.id)
    assert body["sent_cv_at"] is not None
    # The durable human-readable record: version + filename on the timeline,
    # which survives even if the CV row is later deleted (FK is SET NULL).
    assert any(
        "CV sent: backend-focus (cv-backend-focus.pdf)" in n["body"]
        for n in body["notes"]
    )


@pytest.mark.asyncio
async def test_resending_a_different_variant_replaces_current_keeps_history(
    client: AsyncClient, db_session
):
    opp = await _opportunity(client)
    first = await _cv(db_session, "v-general")
    second = await _cv(db_session, "v-platform")

    await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(first.id)}
    )
    r = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(second.id)}
    )
    body = r.json()
    # Current pointer moves; BOTH sends stay on the timeline.
    assert body["sent_cv_id"] == str(second.id)
    sends = [n for n in body["notes"] if n["body"].startswith("CV sent:")]
    assert len(sends) == 2


@pytest.mark.asyncio
async def test_unknown_cv_or_opportunity_is_404_and_records_nothing(
    client: AsyncClient, db_session
):
    opp = await _opportunity(client)
    assert (
        await client.post(
            f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": FAKE_ID}
        )
    ).status_code == 404
    doc = await _cv(db_session, "v-x")
    assert (
        await client.post(
            f"{OPPS}/{FAKE_ID}/cv-sent", json={"cv_document_id": str(doc.id)}
        )
    ).status_code == 404
    # The failed attempt left no partial record.
    body = (await client.get(f"{OPPS}/{opp['id']}")).json()
    assert body["sent_cv_id"] is None
    assert not any(n["body"].startswith("CV sent:") for n in body["notes"])


@pytest.mark.asyncio
async def test_recording_a_send_never_touches_the_public_default(
    client: AsyncClient, db_session
):
    """THE invariant of criterion 4: what the public site serves (`is_active`)
    and what went to one company are independent facts."""
    opp = await _opportunity(client)
    active = await _cv(db_session, "public-default", active=True)
    variant = await _cv(db_session, "tailored-for-acme")

    r = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(variant.id)}
    )
    assert r.status_code == 201

    rows = (await db_session.execute(select(CvDocument))).scalars().all()
    flags = {d.version: d.is_active for d in rows}
    assert flags["public-default"] is True
    assert flags["tailored-for-acme"] is False
    assert active.id != variant.id


@pytest.mark.asyncio
async def test_new_opportunity_starts_with_no_sent_variant(client: AsyncClient):
    opp = await _opportunity(client)
    assert opp["sent_cv_id"] is None
    assert opp["sent_cv_at"] is None
