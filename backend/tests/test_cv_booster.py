import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from app.models.cv_document import CvDocument
from app.config import settings


@pytest.mark.asyncio
async def test_request_cv_exception(client: AsyncClient, db_session):
    # Setup: Ensure an active CV exists to pass the first check
    cv = CvDocument(filename="t.pdf", data=b"d", version="v", is_active=True)
    db_session.add(cv)
    await db_session.commit()

    payload = {"name": "Test", "email": "a@a.com", "message": "hello"}

    # Mock db.add to raise an exception
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=Exception("DB Error")
    ):
        response = await client.post(f"{settings.api_prefix}/cv/request", json=payload)
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to process request"


@pytest.mark.asyncio
async def test_download_cv_tracking_exception(client: AsyncClient, db_session):
    # Setup
    cv = CvDocument(filename="t.pdf", data=b"d", version="v", is_active=True)
    db_session.add(cv)
    await db_session.commit()

    # Mocking select(CvRequest) to fail in tracking part
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_exec:
        # First call for active_cv (part 2 of download_cv) - wait, it's sequential.
        # Actually, let's mock the tracking part logic if we can.
        # Line 78 in cv.py: result = await db.execute(stmt) where stmt is select(CvRequest)

        # We need mock_exec to side_effect: first call raises (for tracking), second call returns active_cv
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cv

        mock_exec.side_effect = [Exception("Tracking Error"), mock_result]

        response = await client.get(f"{settings.api_prefix}/cv/download?req_id=some-id")
        assert response.status_code == 200
        assert response.content == b"d"


@pytest.mark.asyncio
async def test_download_cv_generic_exception(client: AsyncClient, db_session):
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        side_effect=Exception("Generic Error"),
    ):
        response = await client.get(f"{settings.api_prefix}/cv/download")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to download CV"


@pytest.mark.asyncio
async def test_admin_upload_invalid_type(client: AsyncClient):
    files = {"file": ("test.txt", b"content", "text/plain")}
    response = await client.post(
        f"{settings.api_prefix}/admin/cv/upload", files=files, data={"version": "1.0"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


@pytest.mark.asyncio
async def test_admin_upload_success(client: AsyncClient, db_session):
    files = {"file": ("test.pdf", b"pdf data", "application/pdf")}
    response = await client.post(
        f"{settings.api_prefix}/admin/cv/upload", files=files, data={"version": "1.1"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_admin_get_requests_sort_asc(client: AsyncClient, db_session):
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_order=asc"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_get_versions_sort_default(client: AsyncClient, db_session):
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=non_existent"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_upload_exception(client: AsyncClient, db_session):
    files = {"file": ("test.pdf", b"content", "application/pdf")}
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        side_effect=Exception("Upload Error"),
    ):
        response = await client.post(
            f"{settings.api_prefix}/admin/cv/upload",
            files=files,
            data={"version": "1.0"},
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to upload CV"


@pytest.mark.asyncio
async def test_admin_get_requests_sorting_default(client: AsyncClient, db_session):
    # Invalid sort_by should fall back to default
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=non_existent"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_get_requests_exception(client: AsyncClient, db_session):
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        side_effect=Exception("Fetch Error"),
    ):
        response = await client.get(f"{settings.api_prefix}/admin/cv/requests")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to fetch requests"


@pytest.mark.asyncio
async def test_admin_get_versions_full(client: AsyncClient, db_session):
    # Create versions
    v1 = CvDocument(filename="v1.pdf", data=b"d1", version="1.0", is_active=False)
    v2 = CvDocument(filename="v2.pdf", data=b"d2", version="2.0", is_active=True)
    db_session.add_all([v1, v2])
    await db_session.commit()

    # Test sorting and search
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?search=2.0&sort_by=version&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["version"] == "2.0"


@pytest.mark.asyncio
async def test_admin_get_versions_exception(client: AsyncClient, db_session):
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        side_effect=Exception("Versions Error"),
    ):
        response = await client.get(f"{settings.api_prefix}/admin/cv/versions")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to fetch CV versions"


@pytest.mark.asyncio
async def test_email_service_config_missing(db_session):
    from app.services.email import email_service
    from app.config import settings

    with patch.object(settings, "smtp_host", None):
        success = email_service.send_cv_request_notification("N", "e", "C", "M")
        assert success is False

        success = email_service.send_requester_confirmation("N", "e")
        assert success is False


@pytest.mark.asyncio
async def test_email_service_send_exceptions(db_session):
    from app.services.email import email_service
    from app.config import settings

    with (
        patch.object(settings, "smtp_host", "localhost"),
        patch.object(settings, "smtp_user", "user"),
        patch.object(settings, "smtp_password", "pass"),
        patch("smtplib.SMTP", side_effect=Exception("SMTP Error")),
    ):
        success = email_service.send_cv_request_notification("N", "e", "C", "M")
        assert success is False

        success = email_service.send_requester_confirmation("N", "e")
        assert success is False


@pytest.mark.asyncio
async def test_main_infra_check_exception():
    import respx
    from app.main import lifespan
    from fastapi import FastAPI
    from app.config import settings

    app = FastAPI()

    # Mock session and its results for the migration part of lifespan
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = MagicMock()
    mock_session.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    with respx.mock:
        respx.get(f"{settings.ollama_url}/api/tags").side_effect = Exception(
            "Ollama Down"
        )
        with (
            patch("app.main.engine"),
            patch("app.main.async_session", mock_session_factory),
            patch("os.path.exists", return_value=False),
        ):
            async with lifespan(app):
                pass
