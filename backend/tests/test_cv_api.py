import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from app.main import app
from app.models.cv_request import CvRequest
import os

@pytest.mark.asyncio
async def test_cv_request_success(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.cv.process_email_notification", new_callable=AsyncMock) as mock_email:
            payload = {
                "name": "Recruiter One",
                "email": "recruiter@example.com",
                "company": "Big Tech",
                "message": "Interested in your profile."
            }
            response = await ac.post("/api/cv/request", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "/api/cv/download" in data["download_url"]
            
            # Check DB
            result = await db_session.execute(select(CvRequest).where(CvRequest.email == "recruiter@example.com"))
            cv_req = result.scalar_one_or_none()
            assert cv_req is not None
            assert cv_req.name == "Recruiter One"
            
            # Check background task was requested (mocked)
            # Since background tasks run after response, we mocked the function called by it/or the service itself.
            # In FastAPI tests, background tasks are executed.
            # We patched `app.api.cv.process_email_notification` so we verify it was called.
            mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_cv_request_validation_error(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "Recruiter Two",
            # Missing email
            "company": "Startup"
        }
        response = await ac.post("/api/cv/request", json=payload)
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_download_cv_success():
    # Ensure dummy file exists
    os.makedirs("app/static", exist_ok=True)
    with open("app/static/cv.pdf", "w") as f:
        f.write("dummy pdf")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/cv/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

@pytest.mark.asyncio
async def test_download_cv_not_found():
    with patch("os.path.exists", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/cv/download")
            assert response.status_code == 404

import asyncio
# Test the actual background task function to ensure coverage
from app.api.cv import process_email_notification
from app.services.email import EmailService

@pytest.mark.asyncio
async def test_process_email_notification(db_session):
    # Mock specific dependencies
    mock_payload = AsyncMock()
    mock_payload.name = "Test"
    mock_payload.email = "test@example.com" 
    mock_payload.company = "Co" 
    mock_payload.message = "Msg"
    
@pytest.mark.asyncio
async def test_cv_request_exception(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.cv.CvRequest", side_effect=Exception("DB Error")):
            payload = {
                "name": "Recruiter Three",
                "email": "recruiter@example.com",
            }
            response = await ac.post("/api/cv/request", json=payload)
            assert response.status_code == 500
            assert response.json()["detail"] == "Failed to process request"
