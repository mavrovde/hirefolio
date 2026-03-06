import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.cv_request import CvRequest
from app.models.cv_document import CvDocument
from unittest.mock import patch
from app.config import settings


@pytest.mark.asyncio
async def test_cv_request_with_position_description(client: AsyncClient, db_session):
    # Setup: Ensure an active CV document exists
    cv = CvDocument(
        filename="test.pdf", data=b"test data", version="1.0.0", is_active=True
    )
    db_session.add(cv)
    await db_session.commit()

    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "company": "Test Co",
        "message": "Hello, I'm interested.",
        "position_description": "Senior Backend Engineer role at Test Co",
        "subscribe_to_updates": True,
    }

    with (
        patch(
            "app.services.email.email_service.send_cv_request_notification"
        ) as mock_notify,
        patch("app.services.email.email_service.send_requester_confirmation"),
    ):
        response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
        assert response.status_code == 200

        # Verify database
        result = await db_session.execute(
            select(CvRequest).where(CvRequest.email == "test@example.com")
        )
        cv_req = result.scalar_one()
        assert cv_req.position_description == "Senior Backend Engineer role at Test Co"
        assert cv_req.subscribe_to_updates is True

        # Verify email call
        mock_notify.assert_called_once_with(
            name="Test User",
            email="test@example.com",
            company="Test Co",
            message="Hello, I'm interested.",
            position_description="Senior Backend Engineer role at Test Co",
            subscribe_to_updates=True,
        )


@pytest.mark.asyncio
async def test_cv_request_description_max_length(client: AsyncClient, db_session):
    long_desc = "A" * 1001
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "company": "Test Co",
        "message": "Hello",
        "position_description": long_desc,
    }
    response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_admin_get_requests_with_description_search(
    client: AsyncClient, db_session
):
    # Setup: Create a request with a specific description
    cv_req = CvRequest(
        name="Searchable User",
        email="search@example.com",
        company="Search Co",
        message="Message",
        position_description="Unique Description To Search",
        consent_given=True,
    )
    db_session.add(cv_req)
    await db_session.commit()

    # Search for it
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?search=Unique"
    )
    assert response.status_code == 200
    response.json()


@pytest.mark.asyncio
async def test_cv_download_tracking(client: AsyncClient, db_session):
    # Setup
    cv = CvDocument(filename="test.pdf", data=b"data", version="1", is_active=True)
    req = CvRequest(name="U", email="e@e.com", message="m", consent_given=True)
    db_session.add_all([cv, req])
    await db_session.commit()
    await db_session.refresh(req)

    response = await client.get(f"{settings.api_prefix}/cv/download?req_id={req.id}")
    assert response.status_code == 200
    assert response.content == b"data"

    # Check tracking
    await db_session.refresh(req)
    assert req.download_count == 1
    assert req.downloaded_at is not None


@pytest.mark.asyncio
async def test_cv_download_no_active(client: AsyncClient, db_session):
    response = await client.get(f"{settings.api_prefix}/cv/download")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_email_service_logic(db_session):
    from app.services.email import email_service
    from app.config import settings

    # Mock settings to ensure email is "enabled"
    with (
        patch.object(settings, "smtp_host", "localhost"),
        patch.object(settings, "smtp_user", "user"),
        patch.object(settings, "smtp_password", "pass"),
        patch("smtplib.SMTP") as mock_smtp,
    ):
        success = email_service.send_cv_request_notification(
            "Name", "e@e.com", "Co", "Msg", "Pos"
        )
        assert success is True
        mock_smtp.assert_called()

        success = email_service.send_requester_confirmation("Name", "e@e.com")
        assert success is True


@pytest.mark.asyncio
async def test_cv_request_no_active_cv(client: AsyncClient, db_session):
    payload = {"name": "Name", "email": "e@e.com", "message": "message"}
    response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
    assert response.status_code == 404
