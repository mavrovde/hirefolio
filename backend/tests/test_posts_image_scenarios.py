from app.config import settings
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_image_with_no_blob_404(client: AsyncClient, db_session):
    """Scenario: Requesting an image for a post that has no image blob should return 404."""
    post_data = {
        "title": "No Image",
        "slug": "no-image",
        "content": "Content",
    }
    res = await client.post(f"{settings.api_prefix}/posts", json=post_data)
    post_id = res.json()["id"]

    response = await client.get(f"{settings.api_prefix}/posts/{post_id}/image")
    assert response.status_code == 404
