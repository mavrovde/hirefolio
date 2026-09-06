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


@pytest.mark.asyncio
async def test_variant_upload_leaves_the_public_download_unchanged(
    client: AsyncClient,
):
    """The middle clause END-TO-END (#294 review blocker 1): before the
    `activate` flag, uploading a tailored variant unavoidably repointed the
    public site — reproduced with two uploads, the download followed the
    second. Now a variant upload (`activate=false`) leaves it alone, and an
    activating upload still repoints it (the historical default)."""
    from app.config import settings as cfg

    cv_upload = f"{cfg.api_prefix}/admin/cv/upload"
    download = f"{cfg.api_prefix}/cv/download"

    r = await client.post(
        cv_upload,
        files={"file": ("general.pdf", b"%PDF-GENERAL", "application/pdf")},
        data={"version": "general"},
    )
    assert r.status_code == 200
    assert (await client.get(download)).content == b"%PDF-GENERAL"

    r = await client.post(
        cv_upload,
        files={"file": ("acme.pdf", b"%PDF-ACME", "application/pdf")},
        data={"version": "acme-v1", "activate": "false"},
    )
    assert r.status_code == 200
    # THE clause: the public flow still serves the default.
    assert (await client.get(download)).content == b"%PDF-GENERAL"

    # ...and an activating upload still repoints, exactly as before the flag.
    r = await client.post(
        cv_upload,
        files={"file": ("new.pdf", b"%PDF-NEWDEFAULT", "application/pdf")},
        data={"version": "new-default"},
    )
    assert r.status_code == 200
    assert (await client.get(download)).content == b"%PDF-NEWDEFAULT"


@pytest.mark.asyncio
async def test_deleting_the_sent_cv_nulls_the_pointer_and_keeps_the_note(
    client: AsyncClient, db_session
):
    """The SET NULL claim, pinned instead of asserted (#294 review major 3):
    deleting a CV version must not corrupt the opportunity — the pointer goes
    NULL, the human-readable timeline record survives."""
    opp = await _opportunity(client)
    doc = await _cv(db_session, "doomed")
    r = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(doc.id)}
    )
    assert r.status_code == 201

    await db_session.delete(doc)
    await db_session.commit()

    body = (await client.get(f"{OPPS}/{opp['id']}")).json()
    assert body["sent_cv_id"] is None
    assert any("CV sent: doomed (cv-doomed.pdf)" in n["body"] for n in body["notes"])


@pytest.mark.asyncio
async def test_malformed_cv_document_id_is_422(client: AsyncClient):
    opp = await _opportunity(client)
    r = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": "not-a-uuid"}
    )
    assert r.status_code == 422
    assert (
        await client.post(f"{OPPS}/{opp['id']}/cv-sent", json={})
    ).status_code == 422


@pytest.mark.asyncio
async def test_rerecording_the_same_variant_is_deliberate_resend_semantics(
    client: AsyncClient, db_session
):
    """Re-recording the SAME variant appends a second note and moves the
    timestamp — DELIBERATE: sending the same file twice (e.g. to a second
    contact at the company) is a real event the timeline should show
    (#294 review nit 9, answered with an assertion instead of prose)."""
    opp = await _opportunity(client)
    doc = await _cv(db_session, "v-same")
    first = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(doc.id)}
    )
    second = await client.post(
        f"{OPPS}/{opp['id']}/cv-sent", json={"cv_document_id": str(doc.id)}
    )
    body = second.json()
    sends = [n for n in body["notes"] if n["body"].startswith("CV sent:")]
    assert len(sends) == 2
    assert body["sent_cv_at"] >= first.json()["sent_cv_at"]
