import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_post_with_tags(client: AsyncClient):
    """Test creating a post with tags."""
    post_data = {
        "title": "Tagged Post",
        "slug": "tagged-post",
        "content": "Content with tags",
        "language": "en",
        "published": True,
        "tags": ["tag1", "tag2"],
    }

    # client fixture is already authenticated as admin if get_current_user is overridden
    # But we should verify if we need to pass a token or if the override handles it.
    # conftest usually mocks the dependency.
    # Let's assume override works and we don't need header if we use the mocked client.

    response = await client.post("/api/posts", json=post_data)

    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["tag1", "tag2"]
    assert "tag1" in data["tags"]


@pytest.mark.asyncio
async def test_update_post_tags(client: AsyncClient):
    """Test updating post tags."""
    # Create initial post
    post_data = {
        "title": "Update Tags Post",
        "slug": "update-tags-post",
        "content": "Content",
        "tags": ["old"],
    }
    create_resp = await client.post("/api/posts", json=post_data)
    post_id = create_resp.json()["id"]

    # Update
    update_data = {"tags": ["new", "tags"]}
    response = await client.put(f"/api/posts/{post_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["new", "tags"]


@pytest.mark.asyncio
async def test_filter_posts_by_tag(client: AsyncClient):
    """Test filtering posts by tag."""
    # Create posts
    p1 = {
        "title": "Python Post",
        "slug": "python-post",
        "content": "Content",
        "language": "en",
        "published": True,
        "tags": ["python", "coding"],
    }
    p2 = {
        "title": "Rust Post",
        "slug": "rust-post",
        "content": "Content",
        "language": "en",
        "published": True,
        "tags": ["rust", "coding"],
    }

    await client.post("/api/posts", json=p1)
    await client.post("/api/posts", json=p2)

    # Filter by 'python'
    response = await client.get("/api/posts?tag=python")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) >= 1
    assert any(p["slug"] == "python-post" for p in items)
    assert not any(p["slug"] == "rust-post" for p in items)

    # Filter by 'coding' (both)
    response = await client.get("/api/posts?tag=coding")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    slugs = [p["slug"] for p in items]
    assert "python-post" in slugs
    assert "rust-post" in slugs


@pytest.mark.asyncio
async def test_max_tags_validation(client: AsyncClient):
    """Test that max 5 tags are allowed."""
    post_data = {
        "title": "Too Many Tags",
        "slug": "too-many-tags",
        "content": "Content",
        "tags": ["1", "2", "3", "4", "5", "6"],
    }

    response = await client.post("/api/posts", json=post_data)

    assert response.status_code == 422  # Validation Error
