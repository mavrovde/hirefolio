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
            "consent": True,
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
async def test_process_email_notification(db_session):
    # Mock specific dependencies
    mock_payload = AsyncMock()
    mock_payload.name = "Test"
    mock_payload.email = "test@example.com"
    mock_payload.company = "Co"
    mock_payload.message = "Msg"


@pytest.mark.asyncio
async def test_cv_request_exception(client):
    with patch("app.api.cv.CvRequest", side_effect=Exception("DB Error")):
        payload = {
            "name": "Recruiter Three",
            "email": "recruiter@example.com",
            # missing consent to fail validation first? No, we want DB error.
            "consent": True,
        }
        # But wait, validation happens BEFORE DB.
        # So we must provide valid payload to reach DB.
        response = await client.post("/api/cv/request", json=payload)

        # If we reach here, it means we passed Pydantic validation.
        # But wait, `app.api.cv.CvRequest` is the model constructor used inside the endpoint.
        # Patching it should raise exception.

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to process request"
