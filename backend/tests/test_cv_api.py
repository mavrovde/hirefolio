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
        response = await client.post("/api/cv/request", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "/api/cv/download" in data["download_url"]

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
    response = await client.post("/api/cv/request", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cv_request_short_message_422(client):
    payload = {
        "name": "Short Msg",
        "email": "short@example.com",
        "message": "123",  # Too short (min 5)
    }
    response = await client.post("/api/cv/request", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cv_request_no_cv_available_404(client, db_session):
    # Ensure no CV document in DB
    payload = {
        "name": "Fail",
        "email": "fail@example.com",
        "message": "Valid message length",
    }
    response = await client.post("/api/cv/request", json=payload)
    assert response.status_code == 404
    assert "CV_ERROR_UNAVAILABLE" == response.json()["detail"]


@pytest.mark.asyncio
async def test_download_cv_not_found(client, db_session):
    # No CV in DB
    response = await client.get("/api/cv/download")
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

    response = await client.get("/api/cv/download")
    assert response.status_code == 200
    assert response.content == b"db pdf content"


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
        response = await client.post("/api/cv/request", json=payload)

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to process request"
