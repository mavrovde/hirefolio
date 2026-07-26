from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.cv_document import CvDocument


@pytest.fixture
async def mock_db_cv(db_session):
    # Create active CV
    cv = CvDocument(filename="test.pdf", data=b"PDF", version="v1", is_active=True)
    db_session.add(cv)
    await db_session.commit()
    # Skip refresh to avoid session sync issues in tests
    return cv


@pytest.mark.asyncio
async def test_cv_flow(client: AsyncClient, mock_db_cv):
    # Test Request CV (Success)
    with (
        patch("app.services.email.email_service.send_cv_request_notification"),
        patch("app.services.email.email_service.send_requester_confirmation"),
    ):
        resp = await client.post(
            "/api/app/cv/request",
            json={
                "name": "Test User",
                "email": "test@example.com",
                # Fix: message > 5 chars
                "message": "Hello World",
                "subscribe_to_updates": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        download_url = data["download_url"]
        req_id = download_url.split("=")[1]

        # Test Download with ID (Success)
        resp = await client.get(f"/api/app/cv/download?req_id={req_id}")
        assert resp.status_code == 200
        assert resp.content == b"PDF"

        # Test Download without ID (Success)
        resp = await client.get("/api/app/cv/download")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cv_errors(client: AsyncClient, db_session):
    # Test No Active CV
    # Ensure DB is empty of active CVs?
    # The fixture mock_db_cv adds one. We can delete it or prevent fixture use.
    # New test func without fixture.

    # 1. Request without active CV (Fix: message > 5 chars)
    resp = await client.post(
        "/api/app/cv/request",
        json={"name": "Test", "email": "t@t.com", "message": "message"},
    )
    # Should fail 404 because no active CV (mock_db_cv not used)
    assert resp.status_code == 404

    # 2. Download without active CV
    resp = await client.get("/api/app/cv/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_cv_endpoints(client: AsyncClient, mock_db_cv):
    # Test Upload - Invalid Type
    files = {"file": ("test.txt", b"content", "text/plain")}
    resp = await client.post(
        "/api/app/admin/cv/upload", data={"version": "v2"}, files=files
    )
    assert resp.status_code == 400

    # Test Upload - Success
    files = {"file": ("new.pdf", b"NEWPDF", "application/pdf")}
    resp = await client.post(
        "/api/app/admin/cv/upload", data={"version": "v2"}, files=files
    )
    assert resp.status_code == 200

    # Verify old CV deactivated?
    # Logic in endpoint handles it.

    # Test List Requests - Search & Sort
    resp = await client.get(
        "/api/app/admin/cv/requests?search=Test&sort_by=email&sort_order=asc"
    )
    assert resp.status_code == 200

    # Test List Versions
    resp = await client.get("/api/app/admin/cv/versions?search=v2")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cv_download_tracking_error(client: AsyncClient, mock_db_cv):
    # Test download with invalid UUID to trigger exception in tracking
    resp = await client.get("/api/app/cv/download?req_id=invalid-uuid")
    # Should still succeed download, just log warning
    assert resp.status_code == 200
