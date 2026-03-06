import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.models.cv_document import CvDocument
from app.models.cv_request import CvRequest

# Scenario: CV Request Success
# Expected: 200 OK, background task added, DB entry created.


@pytest.mark.asyncio
async def test_scenario_cv_request_success(client: AsyncClient):
    # Mock active CV in DB
    mock_cv = MagicMock(spec=CvDocument)
    mock_cv.version = 1

    # Mock DB execution
    # First query: select(CvDocument).where(is_active)
    # Second query: select(CvRequest)... (in download tracking if requested)
    # Actually, request_cv does:
    # 1. Check active CV
    # 2. Add CvRequest
    # 3. Commit/Refresh

    async def side_effect_execute(stmt):
        # Simplistic match
        if "cv_documents" in str(stmt):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_cv
            return mock_result
        return MagicMock()

    # Mock BackgroundTasks
    # We can't easily mock background tasks logic processed by FastAPI unless we patch `BackgroundTasks.add_task`.
    # But usually we just verify response.

    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=side_effect_execute
    ):
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock
        ):
            with patch(
                "sqlalchemy.ext.asyncio.AsyncSession.refresh", new_callable=AsyncMock
            ):
                with patch(
                    "app.api.cv.process_email_notifications", new_callable=AsyncMock
                ):
                    payload = {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "message": "Hello",
                        "subscribe_to_updates": True,
                    }
                    response = await client.post("/api/app/cv/request", json=payload)
                    assert response.status_code == 200
                    assert response.json()["success"] is True


# Scenario: CV Request Failure (No Active CV)
# Expected: 404 Not Found


@pytest.mark.asyncio
async def test_scenario_cv_request_no_active_cv(client: AsyncClient):
    async def side_effect_execute(stmt):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=side_effect_execute
    ):
        payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Hello",
        }
        response = await client.post("/api/app/cv/request", json=payload)
        assert response.status_code == 404


# Scenario: CV Download Success
# Expected: PDF content, headers


@pytest.mark.asyncio
async def test_scenario_cv_download_success(client: AsyncClient):
    mock_cv = MagicMock(spec=CvDocument)
    mock_cv.data = b"%PDF-1.4..."
    mock_cv.filename = "cv.pdf"

    async def side_effect_execute(stmt):
        if "cv_documents" in str(stmt):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_cv
            return mock_result
        # If req_id provided, it queries CvRequest too.
        if "cv_requests" in str(stmt):
            mock_req = MagicMock(spec=CvRequest)
            mock_req.download_count = 0
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_req
            return mock_result
        return MagicMock()

    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=side_effect_execute
    ):
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock
        ):
            # Test with tracking
            response = await client.get("/api/app/cv/download?req_id=123")
            assert response.status_code == 200
            assert response.content == b"%PDF-1.4..."
            assert "application/pdf" in response.headers["content-type"]
