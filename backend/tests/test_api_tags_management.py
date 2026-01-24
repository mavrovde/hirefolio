import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tags(client: AsyncClient):
    """Test listing all tags with counts."""
    # Create posts with tags
    await client.post(
        "/api/posts",
        json={"title": "P1", "slug": "p1", "content": "c", "tags": ["python", "api"]},
    )
    await client.post(
        "/api/posts",
        json={"title": "P2", "slug": "p2", "content": "c", "tags": ["python", "web"]},
    )

    response = await client.get("/api/tags")
    assert response.status_code == 200
    data = response.json()

    # Verify counts
    tags = {t["name"]: t["count"] for t in data}
    assert tags.get("python") == 2
    assert tags.get("api") == 1
    assert tags.get("web") == 1


@pytest.mark.asyncio
async def test_rename_tag(client: AsyncClient):
    """Test renaming a tag across posts."""
    # Setup
    await client.post(
        "/api/posts",
        json={"title": "P1", "slug": "p1", "content": "c", "tags": ["old-tag"]},
    )

    # Rename
    response = await client.put("/api/tags/old-tag", json={"new_name": "new-tag"})
    assert response.status_code == 200

    # Verify in post
    resp = await client.get("/api/posts/p1")
    assert "new-tag" in resp.json()["tags"]
    assert "old-tag" not in resp.json()["tags"]

    # Verify in list
    tags_resp = await client.get("/api/tags")
    tags = [t["name"] for t in tags_resp.json()]
    assert "new-tag" in tags
    assert "old-tag" not in tags


@pytest.mark.asyncio
async def test_delete_tag(client: AsyncClient):
    """Test deleting a tag from all posts."""
    # Setup
    await client.post(
        "/api/posts",
        json={
            "title": "P1",
            "slug": "p1",
            "content": "c",
            "tags": ["to-delete", "keep"],
        },
    )

    # Delete
    response = await client.delete("/api/tags/to-delete")
    assert response.status_code == 200

    # Verify in post
    resp = await client.get("/api/posts/p1")
    tags = resp.json()["tags"]
    assert "to-delete" not in tags
    assert "keep" in tags
