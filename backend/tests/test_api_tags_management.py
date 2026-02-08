from app.config import settings
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tags(client: AsyncClient):
    """Test listing all tags with counts."""
    # Create posts with tags
    await client.post(
        f"{settings.api_prefix}/posts",
        json={"title": "P1", "slug": "p1", "content": "c", "tags": ["python", "api"]},
    )
    await client.post(
        f"{settings.api_prefix}/posts",
        json={"title": "P2", "slug": "p2", "content": "c", "tags": ["python", "web"]},
    )

    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()

    # Verify counts
    items = data["items"]
    tags = {t["name"]: t["count"] for t in items}
    assert tags.get("python") == 2
    assert tags.get("api") == 1
    assert tags.get("web") == 1


@pytest.mark.asyncio
async def test_rename_tag(client: AsyncClient, db_session):
    """Test renaming a tag across posts."""
    # Setup
    await client.post(
        f"{settings.api_prefix}/posts",
        json={"title": "P1", "slug": "p1-rename", "content": "c", "tags": ["old-tag"]},
    )

    # Rename
    response = await client.put(f"{settings.api_prefix}/tags/old-tag", json={"new_name": "new-tag"})
    assert response.status_code == 200

    # Expire session to reflect DB changes in shared session
    db_session.expire_all()

    # Verify in post
    resp = await client.get(f"{settings.api_prefix}/posts/p1-rename")
    assert "new-tag" in resp.json()["tags"]
    assert "old-tag" not in resp.json()["tags"]

    # Verify in list
    tags_resp = await client.get(f"{settings.api_prefix}/tags")
    tags = [t["name"] for t in tags_resp.json()["items"]]
    assert "new-tag" in tags
    assert "old-tag" not in tags


@pytest.mark.asyncio
async def test_delete_tag(client: AsyncClient, db_session):
    """Test deleting a tag from all posts."""
    # Setup
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "P1",
            "slug": "p1-delete",
            "content": "c",
            "tags": ["to-delete", "keep"],
        },
    )

    # Delete
    response = await client.delete(f"{settings.api_prefix}/tags/to-delete")
    assert response.status_code == 200

    # Expire session to reflect DB changes in shared session
    db_session.expire_all()

    # Verify in post
    resp = await client.get(f"{settings.api_prefix}/posts/p1-delete")
    tags = resp.json()["tags"]
    assert "to-delete" not in tags
    assert "keep" in tags


@pytest.mark.asyncio
async def test_tags_search_and_sort(client: AsyncClient):
    """Test searching and sorting tags in the list endpoint."""
    # Create posts with various tags
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "P1",
            "slug": "p1-tag",
            "content": "c",
            "tags": ["apple", "banana"],
        },
    )
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "P2",
            "slug": "p2-tag",
            "content": "c",
            "tags": ["apple", "cherry"],
        },
    )

    # Search
    response = await client.get(f"{settings.api_prefix}/tags?search=apple")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "apple"
    assert items[0]["count"] == 2

    # Sort by name asc
    response = await client.get(f"{settings.api_prefix}/tags?sort_by=name&sort_order=asc")
    names = [t["name"] for t in response.json()["items"]]
    assert "apple" in names
    assert names.index("apple") < names.index("banana")

    # Sort by count desc
    response = await client.get(f"{settings.api_prefix}/tags?sort_by=count&sort_order=desc")
    items = response.json()["items"]
    assert items[0]["name"] == "apple"
    assert items[0]["count"] == 2
