import pytest
import os
from unittest.mock import AsyncMock, patch
from sqlalchemy.future import select
from app.models.cv_request import CvRequest


@pytest.mark.asyncio
async def test_cv_request_success(client, db_session):
    with patch(
        "app.api.cv.process_email_notification", new_callable=AsyncMock
    ) as mock_email:
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
        assert cv_req.cv_version == "v1.0"

        # Check background task was requested (mocked)
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_cv_request_validation_error(client):
    payload = {
        "name": "Recruiter Two",
        # Missing email
        "company": "Startup",
    }
    response = await client.post("/api/cv/request", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_download_cv_success(client):
    # Ensure dummy file exists
    os.makedirs("app/static", exist_ok=True)
    with open("app/static/cv.pdf", "w") as f:
        f.write("dummy pdf")

    response = await client.get("/api/cv/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_download_cv_not_found(client):
    with patch("os.path.exists", return_value=False):
        response = await client.get("/api/cv/download")
        assert response.status_code == 404


# Test the actual background task function to ensure coverage
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
async def test_process_email_notification_success(db_session):
    from app.api.cv import process_email_notification
    import uuid

    mock_payload = AsyncMock()
    mock_payload.name = "Test"
    mock_payload.email = "test@example.com"
    mock_payload.company = "Co"
    mock_payload.message = "Msg"

    with patch(
        "app.api.cv.email_service.send_cv_request_notification", return_value=True
    ):
        await process_email_notification(uuid.uuid4(), mock_payload, db_session)


@pytest.mark.asyncio
async def test_process_email_notification_failure(db_session):
    from app.api.cv import process_email_notification
    import uuid

    mock_payload = AsyncMock()
    mock_payload.name = "Test"
    mock_payload.email = "test@example.com"
    mock_payload.company = "Co"
    mock_payload.message = "Msg"

    with patch(
        "app.api.cv.email_service.send_cv_request_notification", return_value=False
    ):
        await process_email_notification(uuid.uuid4(), mock_payload, db_session)


@pytest.mark.asyncio
async def test_cv_request_exception(client):
    with patch("app.api.cv.CvRequest", side_effect=Exception("DB Error")):
        payload = {
            "name": "Recruiter Three",
            "email": "recruiter@example.com",
            "message": "Valid message",
        }
        response = await client.post("/api/cv/request", json=payload)

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to process request"
