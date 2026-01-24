import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_posts_empty(client: AsyncClient):
    """Test listing posts when database is empty."""
    response = await client.get("/api/posts")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_post(client: AsyncClient, mock_embedding):
    """Test creating a new post."""
    post_data = {
        "title": "Getting Started with Ollama",
        "slug": "getting-started-ollama",
        "content": "Ollama is a great tool for running LLMs locally...",
        "summary": "Learn how to use Ollama",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.post("/api/posts", json=post_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == post_data["title"]
    assert data["slug"] == post_data["slug"]
    assert data["published"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_post(client: AsyncClient, mock_embedding):
    """Test retrieving a specific post."""
    # Create a post first
    post_data = {
        "title": "Ollama Embeddings",
        "slug": "ollama-embeddings",
        "content": "Using Ollama for embeddings is cost-effective...",
        "summary": "Ollama embeddings guide",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post("/api/posts", json=post_data)

    # Retrieve the post
    response = await client.get("/api/posts/ollama-embeddings")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == post_data["title"]
    assert data["slug"] == post_data["slug"]


@pytest.mark.asyncio
async def test_get_post_not_found(client: AsyncClient):
    """Test retrieving a non-existent post."""
    response = await client.get("/api/posts/non-existent-slug")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_post(client: AsyncClient, mock_embedding):
    """Test updating a post."""
    # Create a post
    post_data = {
        "title": "Original Title",
        "slug": "test-update",
        "content": "Original content",
        "language": "en",
        "published": False,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post("/api/posts", json=post_data)

    # Update the post
    update_data = {
        "title": "Updated Title",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.put("/api/posts/test-update", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["published"] is True


@pytest.mark.asyncio
async def test_delete_post(client: AsyncClient, mock_embedding):
    """Test deleting a post."""
    # Create a post
    post_data = {
        "title": "To Be Deleted",
        "slug": "delete-me",
        "content": "This will be deleted",
        "language": "en",
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post("/api/posts", json=post_data)

    # Delete the post
    response = await client.delete("/api/posts/delete-me")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    # Verify it's gone
    get_response = await client.get("/api/posts/delete-me")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_posts_with_filters(client: AsyncClient, mock_embedding):
    """Test listing posts with language and published filters."""
    posts = [
        {
            "title": "EN Published",
            "slug": "en-pub",
            "content": "Content",
            "language": "en",
            "published": True,
        },
        {
            "title": "EN Draft",
            "slug": "en-draft",
            "content": "Content",
            "language": "en",
            "published": False,
        },
        {
            "title": "DE Published",
            "slug": "de-pub",
            "content": "Inhalt",
            "language": "de",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post("/api/posts", json=post)

    # Test published filter
    response = await client.get("/api/posts?published_only=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(p["published"] for p in data)

    # Test language filter
    response = await client.get("/api/posts?lang=de&published_only=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["language"] == "de"


@pytest.mark.asyncio
async def test_similar_posts(client: AsyncClient, mock_embedding):
    """Test finding similar posts."""
    # Create multiple posts
    posts = [
        {
            "title": "Ollama Guide",
            "slug": "ollama-guide",
            "content": "Ollama tutorial",
            "language": "en",
            "published": True,
        },
        {
            "title": "Docker Tips",
            "slug": "docker-tips",
            "content": "Docker best practices",
            "language": "en",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post("/api/posts", json=post)

    # Get similar posts
    response = await client.get("/api/posts/ollama-guide/similar")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_semantic_search(client: AsyncClient, mock_embedding):
    """Test semantic search."""
    # Create a post
    post_data = {
        "title": "Ollama Semantic Search",
        "slug": "ollama-search",
        "content": "How to implement semantic search with Ollama",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post("/api/posts", json=post_data)

    # Search
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.get(
            "/api/posts/search/semantic?q=semantic+search&lang=en"
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_semantic_search_no_embedding(client: AsyncClient):
    """Test semantic search when embedding service is unavailable."""
    with patch("app.api.posts.get_embedding", return_value=None):
        response = await client.get("/api/posts/search/semantic?q=test")

    assert response.status_code == 400
    assert "unavailable" in response.json()["detail"].lower()
