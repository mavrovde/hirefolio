from app.config import settings
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.future import select
from app.models.cv_request import CvRequest


@pytest.mark.asyncio
async def test_cv_request_success(client, db_session):
    # Ensure active CV exists for versioning
    from app.models.cv_document import CvDocument
    import uuid

    doc = CvDocument(
        id=uuid.uuid4(),
        filename="test.pdf",
        data=b"pdf",
        version="v1.2",
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()

    with patch(
        "app.api.cv.process_email_notifications", new_callable=AsyncMock
    ) as mock_emails:
        payload = {
            "name": "Recruiter One",
            "email": "recruiter@example.com",
            "company": "Big Tech",
            "message": "Interested in your profile.",
        }
        response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert f"{settings.api_prefix}/cv/download" in data["download_url"]

        # Check DB
        result = await db_session.execute(
            select(CvRequest).where(CvRequest.email == "recruiter@example.com")
        )
        cv_req = result.scalar_one_or_none()
        assert cv_req is not None
        assert cv_req.name == "Recruiter One"
        assert cv_req.cv_version == "v1.2"

        # Check background task was requested (mocked)
        mock_emails.assert_called_once()


@pytest.mark.asyncio
async def test_cv_request_validation_error(client):
    payload = {
        "name": "Recruiter Two",
        # Missing email
        "company": "Startup",
        "message": "Valid message",
    }
    response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cv_request_short_message_422(client):
    payload = {
        "name": "Short Msg",
        "email": "short@example.com",
        "message": "123",  # Too short (min 5)
    }
    response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cv_request_no_cv_available_404(client, db_session):
    # Ensure no CV document in DB
    payload = {
        "name": "Fail",
        "email": "fail@example.com",
        "message": "Valid message length",
    }
    response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
    assert response.status_code == 404
    assert "CV_ERROR_UNAVAILABLE" == response.json()["detail"]


@pytest.mark.asyncio
async def test_download_cv_not_found(client, db_session):
    # No CV in DB
    response = await client.get(f"{settings.api_prefix}/cv/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "CV_ERROR_UNAVAILABLE"


@pytest.mark.asyncio
async def test_download_cv_db_success(client, db_session):
    # Add a document to DB
    from app.models.cv_document import CvDocument
    import uuid

    doc = CvDocument(
        id=uuid.uuid4(),
        filename="test.pdf",
        data=b"db pdf content",
        version="v1.0",
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/cv/download")
    assert response.status_code == 200
    assert response.content == b"db pdf content"


@pytest.mark.asyncio
async def test_download_cv_with_tracking(client, db_session):
    # Setup CV and Request
    from app.models.cv_document import CvDocument
    from app.models.cv_request import CvRequest
    import uuid

    doc = CvDocument(
        id=uuid.uuid4(),
        filename="track.pdf",
        data=b"pdf data",
        version="v1.3",
        is_active=True,
    )
    db_session.add(doc)

    req_id = uuid.uuid4()
    req = CvRequest(
        id=req_id,
        name="Tracker",
        email="track@example.com",
        message="Tracking test",
        cv_version="v1.3",
        consent_given=True,
    )
    db_session.add(req)
    await db_session.commit()

    # Download with req_id
    response = await client.get(f"{settings.api_prefix}/cv/download?req_id={str(req_id)}")
    assert response.status_code == 200
    assert response.content == b"pdf data"

    # Verify tracking
    # Start a new transaction/session to ensure we see the update
    # Note: In pytest-asyncio with shared session, refresh should work if commit happened.
    # We might need to handle session expiry or isolation depending on fixture.
    # Assuming 'db_session' fixture commits or flushes correctly.

    # Re-fetch from DB
    result = await db_session.execute(select(CvRequest).where(CvRequest.id == req_id))
    updated_req = result.scalar_one()

    assert updated_req.download_count == 1
    assert updated_req.downloaded_at is not None


@pytest.mark.asyncio
async def test_process_email_notifications_calls_both(db_session):
    from app.api.cv import process_email_notifications
    import uuid

    mock_payload = AsyncMock()
    mock_payload.name = "Test"
    mock_payload.email = "test@example.com"
    mock_payload.company = "Co"
    mock_payload.message = "Msg"

    with (
        patch("app.api.cv.email_service.send_cv_request_notification") as mock_admin,
        patch("app.api.cv.email_service.send_requester_confirmation") as mock_user,
    ):
        await process_email_notifications(uuid.uuid4(), mock_payload)
        mock_admin.assert_called_once()
        mock_user.assert_called_once()


@pytest.mark.asyncio
async def test_cv_request_exception(client):
    with patch("app.api.cv.select", side_effect=Exception("DB Error")):
        payload = {
            "name": "Recruiter Three",
            "email": "recruiter@example.com",
            "message": "Valid message long",
        }
        response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to process request"


@pytest.mark.asyncio
async def test_download_cv_exception(client):
    with patch("app.api.cv.select", side_effect=Exception("DB Error")):
        response = await client.get(f"{settings.api_prefix}/cv/download")
        assert response.status_code == 500
