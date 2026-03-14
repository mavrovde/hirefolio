from app.config import settings
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_post_duplicate_slug_retry(client: AsyncClient, mock_embedding, mocker):
    """Scenario: Creating a post with an existing slug should retry and append a random suffix."""
    post_data = {
        "title": "Unique Title",
        "slug": "collision-slug",
        "content": "Content",
        "language": "en",
        "published": True,
    }
    await client.post(f"{settings.api_prefix}/posts", json=post_data)

    # Collision creation
    response = await client.post(f"{settings.api_prefix}/posts", json=post_data)
    
    assert response.status_code == 200
    assert response.json()["slug"].startswith("collision-slug-")
    assert response.json()["slug"] != "collision-slug"
