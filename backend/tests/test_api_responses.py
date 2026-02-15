from app.config import settings
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_posts_with_data(client: AsyncClient, mock_embedding, mocker):
    """Test listing posts returns proper response format."""
    posts = [
        {
            "title": "Test Post 1",
            "slug": "test-1",
            "content": "Content 1",
            "summary": "Summary 1",
            "language": "en",
            "published": True,
        },
        {
            "title": "Test Post 2",
            "slug": "test-2",
            "content": "Content 2",
            "summary": "Summary 2",
            "language": "de",
            "published": False,
        },
    ]


    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    # Test default (published only)
    response = await client.get(f"{settings.api_prefix}/posts")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Test Post 1"
    assert "id" in items[0]
    assert "created_at" in items[0]

    # Test with language filter
    response = await client.get(f"{settings.api_prefix}/posts?lang=de&published_only=false")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["language"] == "de"


@pytest.mark.asyncio
async def test_get_post_full_response(client: AsyncClient, mock_embedding, mocker):
    """Test get post returns full response with all fields."""
    post_data = {
        "title": "Full Response Test",
        "slug": "full-response",
        "content": "This is the full content",
        "summary": "This is a summary",
        "language": "en",
        "published": True,
    }


    create_response = await client.post(f"{settings.api_prefix}/posts", json=post_data)

    # Verify create response has all fields
    created = create_response.json()
    assert "id" in created
    assert "created_at" in created
    assert "updated_at" in created
    assert created["title"] == post_data["title"]
    assert created["content"] == post_data["content"]
    assert created["summary"] == post_data["summary"]

    # Get the post
    response = await client.get(f"{settings.api_prefix}/posts/full-response")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["title"] == post_data["title"]
    assert data["content"] == post_data["content"]
    assert data["summary"] == post_data["summary"]
    assert data["language"] == post_data["language"]
    assert data["published"] is True
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_update_post_full_response(client: AsyncClient, mock_embedding, mocker):
    """Test update returns full response."""
    # Create
    post_data = {
        "title": "Original",
        "slug": "update-test",
        "content": "Original content",
        "summary": "Original summary",
        "language": "en",
        "published": False,
    }


    create_resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
    post_id = create_resp.json()["id"]

    # Update with all fields
    update_data = {
        "title": "Updated Title",
        "content": "Updated content",
        "summary": "Updated summary",
        "language": "de",
        "published": True,
    }

    response = await client.put(f"{settings.api_prefix}/posts/{post_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Updated content"
    assert data["summary"] == "Updated summary"
    assert data["language"] == "de"
    assert data["published"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_similar_posts_with_results(client: AsyncClient, mock_embedding, mocker):
    """Test similar posts returns proper response format."""
    posts = [
        {
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content",
            "summary": "Sum 1",
            "language": "en",
            "published": True,
        },
        {
            "title": "Post 2",
            "slug": "post-2",
            "content": "Content",
            "summary": "Sum 2",
            "language": "en",
            "published": True,
        },
        {
            "title": "Post 3",
            "slug": "post-3",
            "content": "Content",
            "summary": "Sum 3",
            "language": "en",
            "published": True,
        },
    ]


    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    response = await client.get(f"{settings.api_prefix}/posts/post-1/similar?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should return similar posts
    for item in data:
        assert "id" in item
        assert "title" in item
        assert "slug" in item
        assert "similarity" in item
        assert item["slug"] != "post-1"  # Should not include the original
