import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_suggest_tags_endpoint(client: AsyncClient):
    """Test suggest tags endpoint with mocked AI service."""
    mock_tags = ["mocked", "ai", "tags"]

    with patch("app.services.ai.suggest_tags", return_value=mock_tags) as mock_suggest:
        response = await client.post(
            "/api/posts/suggest-tags",
            json={"title": "Test Title", "content": "Test Content"},
        )

        assert response.status_code == 200
        assert response.json() == {"tags": mock_tags}
        mock_suggest.assert_called_once()


@pytest.mark.asyncio
async def test_suggest_tags_unauthorized(client: AsyncClient):
    """Test suggest tags endpoint without authentication."""
    # Create a new client without auth headers (default client in conftest usually has them)
    # We'll just manually clear headers if the fixture sets them, or use a fresh client.
    # Assuming 'client' fixture is authorized admin user based on other tests.
    
    # We can use a fresh client:
    async with AsyncClient(base_url="http://test") as ac:
         response = await ac.post(
            "/api/posts/suggest-tags",
            json={"title": "Test", "content": "Test"},
        )
         # Should be 401 Unauthorized
         assert response.status_code == 401


@pytest.mark.asyncio
async def test_suggest_tags_service_failure(client: AsyncClient):
    """Test suggest tags when AI service fails (returns empty)."""
    with patch("app.services.ai.suggest_tags", return_value=[]):
        response = await client.post(
            "/api/posts/suggest-tags",
            json={"title": "Test", "content": "Test"},
        )
        assert response.status_code == 200
        assert response.json() == {"tags": []}


@pytest.mark.asyncio
async def test_suggest_tags_validation(client: AsyncClient):
    """Test validation errors for missing fields."""
    response = await client.post(
        "/api/posts/suggest-tags",
        json={"title": "Only Title"},  # Missing content
    )
    assert response.status_code == 422

