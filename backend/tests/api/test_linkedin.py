from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.auth import get_current_admin_user

# Mock user for dependency override
mock_admin_user = MagicMock()
mock_admin_user.id = 1
mock_admin_user.username = "admin"
mock_admin_user.is_admin = True


@pytest.fixture
def override_get_current_admin_user():
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_admin_user, None)


@pytest.mark.asyncio
async def test_sync_linkedin_profile_success(override_get_current_admin_user):
    expected_data = {"name": "Test User"}
    with patch(
        "app.api.linkedin.linkedin_service.sync_profile", new_callable=AsyncMock
    ) as mock_sync:
        mock_sync.return_value = expected_data
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/profile-sync")
            assert response.status_code == 200
            assert response.json() == expected_data


@pytest.mark.asyncio
async def test_sync_linkedin_profile_value_error(
    override_get_current_admin_user, caplog
):
    with (
        patch(
            "app.api.linkedin.linkedin_service.sync_profile", new_callable=AsyncMock
        ) as mock_sync,
        caplog.at_level("ERROR"),
    ):
        mock_sync.side_effect = ValueError("Config missing: /secret/path/creds.json")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/profile-sync")
            assert response.status_code == 500
            detail = response.json()["detail"]
            assert detail == "LinkedIn config error."
            assert "/secret/path/creds.json" not in detail
            assert "/secret/path/creds.json" in caplog.text


@pytest.mark.asyncio
async def test_sync_linkedin_profile_generic_error(
    override_get_current_admin_user, caplog
):
    with (
        patch(
            "app.api.linkedin.linkedin_service.sync_profile", new_callable=AsyncMock
        ) as mock_sync,
        caplog.at_level("ERROR"),
    ):
        mock_sync.side_effect = Exception("Unknown: driver stack trace XYZ")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/profile-sync")
            assert response.status_code == 500
            detail = response.json()["detail"]
            assert detail == "LinkedIn profile sync failed."
            assert "driver stack trace XYZ" not in detail
            assert "driver stack trace XYZ" in caplog.text


@pytest.mark.asyncio
async def test_get_linkedin_posts_success(override_get_current_admin_user):
    expected_data = [{"content": "Hello"}]
    with patch(
        "app.api.linkedin.linkedin_service.fetch_posts", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = expected_data
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/posts")
            assert response.status_code == 200
            assert response.json() == expected_data


@pytest.mark.asyncio
async def test_get_linkedin_posts_value_error(override_get_current_admin_user):
    with patch(
        "app.api.linkedin.linkedin_service.fetch_posts", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = ValueError("Config missing")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/posts")
            assert response.status_code == 200
            assert response.json() == []


@pytest.mark.asyncio
async def test_get_linkedin_posts_generic_error(
    override_get_current_admin_user, caplog
):
    with (
        patch(
            "app.api.linkedin.linkedin_service.fetch_posts", new_callable=AsyncMock
        ) as mock_fetch,
        caplog.at_level("ERROR"),
    ):
        mock_fetch.side_effect = Exception("Unknown: scraper internals leaked")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/posts")
            assert response.status_code == 500
            detail = response.json()["detail"]
            assert detail == "LinkedIn posts fetch failed."
            assert "scraper internals leaked" not in detail
            assert "scraper internals leaked" in caplog.text


@pytest.mark.asyncio
async def test_transfer_linkedin_post_success(override_get_current_admin_user):
    post_data = {
        "content": "This is a test linkedin post",
        "image_url": "http://image.com",
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-post", json=post_data
                )
                assert response.status_code == 200
                assert response.json()["message"] == "Post transferred successfully"
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_linkedin_post_empty_title_fallback(
    override_get_current_admin_user,
):
    post_data = {"content": ""}

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-post", json=post_data
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_linkedin_post_long_content_fallback(
    override_get_current_admin_user,
):
    post_data = {
        # start with a bunch of non alphanumeric characters that might get stripped and result in empty slug base if not handled
        "content": "!!! " + "A" * 60
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-post", json=post_data
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_linkedin_post_db_error(override_get_current_admin_user, caplog):
    post_data = {"content": "Test DB Error"}

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(
        side_effect=Exception("DB Error: connection to 10.0.0.5")
    )
    mock_db.rollback = AsyncMock()

    with (
        patch("app.api.linkedin.get_db", return_value=mock_db),
        patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed,
        caplog.at_level("ERROR"),
    ):
        mock_embed.return_value = [0.1, 0.2]

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-post", json=post_data
                )
                assert response.status_code == 500
                detail = response.json()["detail"]
                assert detail == "Transfer failed."
                assert "10.0.0.5" not in detail
                assert "10.0.0.5" in caplog.text
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_post_with_image(override_get_current_admin_user):
    """Test transferring a post with an image URL."""
    post_data = {
        "content": "Post with a LinkedIn image attached",
        "image_url": "https://media.licdn.com/dms/image/test.jpg",
        "urn": "urn:li:activity:99999",
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-post", json=post_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Post transferred successfully"

                # Verify the Post object was created with the image_url
                added_post = mock_db.add.call_args[0][0]
                assert (
                    added_post.image_url == "https://media.licdn.com/dms/image/test.jpg"
                )
                assert added_post.tags == ["LinkedIn"]
                assert added_post.published is False
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_posts_bulk_success(override_get_current_admin_user):
    """Test bulk transfer of multiple LinkedIn posts."""
    posts_data = [
        {"content": "First post content", "image_url": "https://img1.jpg"},
        {"content": "Second post content", "urn": "urn:li:activity:111"},
        {"content": "Third post no image"},
    ]

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-posts", json=posts_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["transferred"] == 3
                assert "ids" in data
                assert "Successfully transferred 3 posts" in data["message"]
                # 3 posts were added
                assert mock_db.add.call_count == 3
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_posts_bulk_empty(override_get_current_admin_user):
    """Test bulk transfer with empty list."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-posts", json=[]
                )
                assert response.status_code == 200
                data = response.json()
                assert data["transferred"] == 0
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_transfer_posts_bulk_db_error(override_get_current_admin_user, caplog):
    """Test bulk transfer with DB error rolls back."""
    posts_data = [
        {"content": "Post that will fail"},
    ]

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(side_effect=Exception("DB bulk error: /var/lib/pg/wal"))
    mock_db.rollback = AsyncMock()
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed,
        caplog.at_level("ERROR"),
    ):
        mock_embed.return_value = [0.1, 0.2]
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/app/linkedin/transfer-posts", json=posts_data
                )
                assert response.status_code == 500
                detail = response.json()["detail"]
                assert detail == "Bulk transfer failed."
                assert "/var/lib/pg/wal" not in detail
                assert "/var/lib/pg/wal" in caplog.text
                mock_db.rollback.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_linkedin_success(override_get_current_admin_user):
    login_data = {"username": "test@test.com", "password": "password"}
    with patch(
        "app.api.linkedin.linkedin_service.login", new_callable=AsyncMock
    ) as mock_login:
        mock_login.return_value = True
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/app/linkedin/login", json=login_data)
            assert response.status_code == 200
            assert "Successfully logged in" in response.json()["message"]


@pytest.mark.asyncio
async def test_login_linkedin_failure(override_get_current_admin_user):
    login_data = {"username": "test@test.com", "password": "password"}
    with patch(
        "app.api.linkedin.linkedin_service.login", new_callable=AsyncMock
    ) as mock_login:
        mock_login.return_value = False
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/app/linkedin/login", json=login_data)
            assert response.status_code == 401
            assert (
                "Login failed. Check credentials and MFA." in response.json()["detail"]
            )


@pytest.mark.asyncio
async def test_login_linkedin_exception(override_get_current_admin_user, caplog):
    """The raw exception must never reach the client — only a generic detail,
    with the full exception logged server-side instead."""
    login_data = {"username": "test@test.com", "password": "password"}
    with (
        patch(
            "app.api.linkedin.linkedin_service.login", new_callable=AsyncMock
        ) as mock_login,
        caplog.at_level("ERROR"),
    ):
        mock_login.side_effect = Exception("Challenge required: internal driver X")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/app/linkedin/login", json=login_data)
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert detail == "LinkedIn login failed. Check credentials and MFA."
            assert "Challenge required: internal driver X" not in detail
            assert "Challenge required: internal driver X" in caplog.text


@pytest.mark.asyncio
async def test_get_linkedin_status(override_get_current_admin_user):
    with patch(
        "app.api.linkedin.linkedin_service.is_logged_in", new_callable=AsyncMock
    ) as mock_status:
        mock_status.return_value = True
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/status")
            assert response.status_code == 200
            assert response.json()["logged_in"] is True
