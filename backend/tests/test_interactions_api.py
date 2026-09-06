"""Recruiter communication hub tests (#69)."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.cv_document import CvDocument
from app.models.interaction import Interaction

CONTACT_URL = f"{settings.api_prefix}/interactions/contact"
ADMIN_URL = f"{settings.api_prefix}/admin/interactions"


async def _post_contact(client: AsyncClient, **overrides):
    body = {
        "name": "Rita Recruiter",
        "email": "rita@agency.example",
        "company": "Agency GmbH",
        "message": "We have a role you would be perfect for.",
    }
    body.update(overrides)
    return await client.post(CONTACT_URL, json=body)


# --- public contact form -----------------------------------------------------


@pytest.mark.asyncio
async def test_contact_creates_interaction(client: AsyncClient, db_session):
    resp = await _post_contact(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "contact_form"
    assert data["status"] == "new"
    assert data["name"] == "Rita Recruiter"

    row = (await db_session.execute(select(Interaction))).scalars().all()
    assert len(row) == 1
    assert row[0].email == "rita@agency.example"


@pytest.mark.asyncio
async def test_contact_sends_notification_in_background(client: AsyncClient):
    with patch(
        "app.api.interactions.EmailService.send_interaction_notification"
    ) as send:
        resp = await _post_contact(client)
        assert resp.status_code == 201
    send.assert_called_once()
    assert send.call_args.kwargs["source"] == "contact_form"


@pytest.mark.asyncio
async def test_contact_notification_failure_never_breaks_intake(client: AsyncClient):
    with patch(
        "app.api.interactions.EmailService.send_interaction_notification",
        side_effect=RuntimeError("smtp down"),
    ):
        resp = await _post_contact(client)
    assert resp.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"email": "not-an-email"},
        {"message": ""},
        {"name": "x" * 201},
        {"message": "x" * 10_001},
        {"name": "   "},
        {"name": "A"},
        {"name": " A \n "},
        {"message": " \n\t  "},
        {"message": "hi  "},
        {"company": "x" * 201},
    ],
)
async def test_contact_validation_errors(client: AsyncClient, overrides):
    resp = await _post_contact(client, **overrides)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contact_accepts_unicode_identity(client: AsyncClient):
    resp = await _post_contact(
        client,
        name="Zo\u00eb M\u00fcller \u6d4b\u8bd5",
        company="M\u00fcller & S\u00f6hne",
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Zo\u00eb M\u00fcller \u6d4b\u8bd5"


@pytest.mark.asyncio
async def test_contact_folds_line_breaks_in_header_bound_fields(client: AsyncClient):
    """A line break in `name` reaches the notification's Subject header, where the
    stdlib refuses the whole email — the API folds it to spaces BEFORE storage and
    notification, so the owner still gets notified (review finding, #69 round 1)."""
    with patch(
        "app.api.interactions.EmailService.send_interaction_notification"
    ) as send:
        resp = await _post_contact(
            client,
            name="Eve\r\nBcc: spam@x",
            company="A\nB",
            message="A perfectly fine message.",
        )
        assert resp.status_code == 201
    assert resp.json()["name"] == "Eve Bcc: spam@x"
    assert resp.json()["company"] == "A B"
    sent_name = send.call_args.kwargs["name"]
    assert "\n" not in sent_name and "\r" not in sent_name


@pytest.mark.asyncio
async def test_contact_rate_limited_after_limit(client: AsyncClient, monkeypatch):
    """The public contact form is a WRITE (DB row + owner email) — the Nth request
    inside the window gets 429 and creates neither (review blocker, #69 round 1)."""
    from app.api import interactions as interactions_module

    monkeypatch.setattr(interactions_module.contact_rate_limiter, "max_requests", 3)
    with patch(
        "app.api.interactions.EmailService.send_interaction_notification"
    ) as send:
        for _ in range(3):
            assert (await _post_contact(client)).status_code == 201
        resp = await _post_contact(client)
        assert resp.status_code == 429
    assert send.call_count == 3


@pytest.mark.asyncio
async def test_admin_inbox_empty_first_visit(client: AsyncClient):
    """A brand-new deployment's inbox: no rows, sane pagination, no errors."""
    resp = await client.get(ADMIN_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"items": [], "total": 0, "page": 1, "pages": 1}


# --- CV request indexing (#69 wiring) ---------------------------------------


@pytest.mark.asyncio
async def test_cv_request_indexed_in_inbox(client: AsyncClient, db_session):
    db_session.add(
        CvDocument(filename="cv.pdf", data=b"%PDF-1.4", version="t", is_active=True)
    )
    await db_session.commit()

    resp = await client.post(
        f"{settings.api_prefix}/cv/request",
        json={
            "name": "Carl Curious",
            "email": "carl@corp.example",
            "company": "Corp",
            "message": "CV please",
            "position_description": "Staff role",
            "subscribe_to_updates": False,
        },
    )
    assert resp.status_code == 200

    rows = (
        (
            await db_session.execute(
                select(Interaction).where(Interaction.source == "cv_request")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].source_ref is not None
    assert rows[0].payload["position_description"] == "Staff role"


@pytest.mark.asyncio
async def test_cv_request_survives_inbox_indexing_failure(
    client: AsyncClient, db_session
):
    """The inbox is an index, never a gate: if creating the Interaction blows
    up, the CV request itself must still succeed (cv.py's guarded block)."""
    db_session.add(
        CvDocument(filename="cv.pdf", data=b"%PDF-1.4", version="t", is_active=True)
    )
    await db_session.commit()

    with patch(
        "app.models.interaction.Interaction.__init__",
        side_effect=RuntimeError("inbox down"),
    ):
        resp = await client.post(
            f"{settings.api_prefix}/cv/request",
            json={
                "name": "Carla Careful",
                "email": "carla@corp.example",
                "company": "Corp",
                "message": "CV please",
                "position_description": None,
                "subscribe_to_updates": False,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# --- admin inbox --------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_requires_auth(clean_client: AsyncClient):
    resp = await clean_client.get(ADMIN_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_filters_and_pagination(client: AsyncClient, db_session):
    for i in range(3):
        await _post_contact(client, name=f"Person {i}", message=f"message {i}")
    # one closed row to filter against
    row = (await db_session.execute(select(Interaction))).scalars().first()
    row.status = "closed"
    await db_session.commit()

    all_resp = (await client.get(ADMIN_URL)).json()
    assert all_resp["total"] == 3
    # newest first
    assert all_resp["items"][0]["name"] == "Person 2"

    closed = (await client.get(f"{ADMIN_URL}?status=closed")).json()
    assert closed["total"] == 1

    paged = (await client.get(f"{ADMIN_URL}?page=2&page_size=1")).json()
    assert paged["page"] == 2 and paged["pages"] == 3 and len(paged["items"]) == 1

    src = (await client.get(f"{ADMIN_URL}?source=contact_form")).json()
    assert src["total"] == 3


@pytest.mark.asyncio
async def test_admin_list_rejects_unknown_filters(client: AsyncClient):
    assert (await client.get(f"{ADMIN_URL}?status=bogus")).status_code == 422
    assert (await client.get(f"{ADMIN_URL}?source=bogus")).status_code == 422


@pytest.mark.asyncio
async def test_admin_status_workflow(client: AsyncClient):
    created = (await _post_contact(client)).json()
    iid = created["id"]

    for status in ("contacted", "in_progress", "closed"):
        resp = await client.patch(f"{ADMIN_URL}/{iid}", json={"status": status})
        assert resp.status_code == 200
        assert resp.json()["status"] == status

    # persisted
    listed = (await client.get(f"{ADMIN_URL}?status=closed")).json()
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_admin_patch_unknown_status_and_missing_id(client: AsyncClient):
    created = (await _post_contact(client)).json()
    assert (
        await client.patch(f"{ADMIN_URL}/{created['id']}", json={"status": "nope"})
    ).status_code == 422
    assert (
        await client.patch(
            f"{ADMIN_URL}/00000000-0000-0000-0000-000000000000",
            json={"status": "closed"},
        )
    ).status_code == 404


# --- email service ------------------------------------------------------------


def test_interaction_notification_skips_without_smtp(monkeypatch):
    from app.services.email import EmailService

    monkeypatch.setattr(settings, "smtp_host", "")
    assert (
        EmailService().send_interaction_notification(
            source="contact_form", name="n", email="e@x", company="", message="m"
        )
        is False
    )


def test_interaction_notification_sends_via_smtp(monkeypatch):
    from app.services.email import EmailService

    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_user", "u")
    monkeypatch.setattr(settings, "smtp_password", "p")
    with patch("app.services.email.smtplib.SMTP") as smtp:
        ok = EmailService().send_interaction_notification(
            source="cv_request", name="n", email="e@x", company="C", message="m"
        )
    assert ok is True
    smtp.assert_called_once_with(
        "smtp.test", settings.smtp_port, timeout=settings.smtp_timeout_seconds
    )


def test_interaction_notification_smtp_error_returns_false(monkeypatch):
    from app.services.email import EmailService

    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_user", "u")
    monkeypatch.setattr(settings, "smtp_password", "p")
    with patch("app.services.email.smtplib.SMTP", side_effect=OSError("conn refused")):
        ok = EmailService().send_interaction_notification(
            source="contact_form", name="n", email="e@x", company="", message="m"
        )
    assert ok is False
