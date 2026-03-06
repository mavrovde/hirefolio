import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.auth import get_current_admin_user
from unittest.mock import patch, MagicMock, AsyncMock

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
async def test_sync_linkedin_profile_value_error(override_get_current_admin_user):
    with patch(
        "app.api.linkedin.linkedin_service.sync_profile", new_callable=AsyncMock
    ) as mock_sync:
        mock_sync.side_effect = ValueError("Config missing")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/profile-sync")
            assert response.status_code == 500
            assert "LinkedIn config error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sync_linkedin_profile_generic_error(override_get_current_admin_user):
    with patch(
        "app.api.linkedin.linkedin_service.sync_profile", new_callable=AsyncMock
    ) as mock_sync:
        mock_sync.side_effect = Exception("Unknown")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/profile-sync")
            assert response.status_code == 500
            assert "LinkedIn profile sync failed" in response.json()["detail"]


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
async def test_get_linkedin_posts_generic_error(override_get_current_admin_user):
    with patch(
        "app.api.linkedin.linkedin_service.fetch_posts", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("Unknown")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/app/linkedin/posts")
            assert response.status_code == 500
            assert "LinkedIn posts fetch failed" in response.json()["detail"]


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
async def test_transfer_linkedin_post_db_error(override_get_current_admin_user):
    post_data = {"content": "Test DB Error"}

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
    mock_db.rollback = AsyncMock()

    with (
        patch("app.api.linkedin.get_db", return_value=mock_db),
        patch("app.api.linkedin.get_embedding", new_callable=AsyncMock) as mock_embed,
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
                assert "Transfer failed" in response.json()["detail"]
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
async def test_transfer_posts_bulk_db_error(override_get_current_admin_user):
    """Test bulk transfer with DB error rolls back."""
    posts_data = [
        {"content": "Post that will fail"},
    ]

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(side_effect=Exception("DB bulk error"))
    mock_db.rollback = AsyncMock()
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
                assert response.status_code == 500
                assert "Bulk transfer failed" in response.json()["detail"]
                mock_db.rollback.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_db, None)
