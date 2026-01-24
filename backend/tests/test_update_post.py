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
    resp = await client.post("/api/posts", json=create_data)
    assert resp.status_code == 200

    # 2. Update
    update_data = {"title": "Updated Title", "content": "Updated Content"}
    resp_update = await client.put(f"/api/posts/{slug}", json=update_data)
    assert resp_update.status_code == 200
    updated_post = resp_update.json()
    assert updated_post["title"] == "Updated Title"
    assert updated_post["content"] == "Updated Content"

    # 3. Verify Persistence
    resp_get = await client.get(f"/api/posts/{slug}")
    assert resp_get.status_code == 200
    assert resp_get.json()["title"] == "Updated Title"
