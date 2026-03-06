from app.config import settings
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_post_flow(client: AsyncClient):
    """Test full update flow: Create -> Update -> Verify."""
    # 1. Create
    slug = "test-update-slug"
    create_data = {
        "title": "Original Title",
        "slug": slug,
        "content": "Original Content",
        "published": True,
        "language": "en",
    }
    resp = await client.post(f"{settings.api_prefix}/posts", json=create_data)
    assert resp.status_code == 200
    post_id = resp.json()["id"]

    # 2. Update
    update_data = {"title": "Updated Title", "content": "Updated Content"}
    resp_update = await client.put(
        f"{settings.api_prefix}/posts/{post_id}", json=update_data
    )
    assert resp_update.status_code == 200
    updated_post = resp_update.json()
    assert updated_post["title"] == "Updated Title"
    assert updated_post["content"] == "Updated Content"

    # 3. Verify Persistence
    # Verify by ID
    resp_get_id = await client.get(f"{settings.api_prefix}/posts/{post_id}")
    assert resp_get_id.status_code == 200
    assert resp_get_id.json()["title"] == "Updated Title"

    # Verify by Slug
    resp_get_slug = await client.get(f"{settings.api_prefix}/posts/{slug}")
    assert resp_get_slug.status_code == 200
    assert resp_get_slug.json()["title"] == "Updated Title"
