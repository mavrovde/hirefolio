import pytest
from unittest.mock import patch
from httpx import AsyncClient
from app.models.user import User

# Mock User object
mock_admin_user = User(
    id=1, username="admin", email="admin@example.com", is_admin=True, is_active=True
)


@pytest.mark.asyncio
async def test_complete_post_workflow(client: AsyncClient, mock_embedding):
    """Test complete post lifecycle: create -> retrieve -> update -> search -> delete."""

    # 1. Create a post
    post_data = {
        "title": "Complete Guide to Ollama",
        "slug": "complete-ollama-guide",
        "content": "This is a comprehensive guide about using Ollama for local LLM inference and embeddings.",
        "summary": "Learn everything about Ollama",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        create_response = await client.post("/api/posts", json=post_data)

        assert create_response.status_code == 200
        created_post = create_response.json()
        assert created_post["title"] == post_data["title"]
        post_id = created_post["id"]

        # 2. Retrieve the post
        get_response = await client.get(f"/api/posts/{post_data['slug']}")
        assert get_response.status_code == 200
        retrieved_post = get_response.json()
        assert retrieved_post["id"] == post_id
        assert retrieved_post["content"] == post_data["content"]

        # 3. Update the post
        update_data = {
            "title": "Updated: Complete Guide to Ollama",
            "summary": "Updated summary",
        }

        update_response = await client.put(
            f"/api/posts/{post_id}", json=update_data
        )

        assert update_response.status_code == 200
        updated_post = update_response.json()
        assert updated_post["title"] == update_data["title"]
        assert updated_post["summary"] == update_data["summary"]

        # 4. Search for the post
        search_response = await client.get(
            "/api/posts/search/semantic?q=ollama+guide&lang=en"
        )

        assert search_response.status_code == 200
        search_results = search_response.json()
        assert isinstance(search_results, list)

        # 5. Delete the post
        delete_response = await client.delete(f"/api/posts/{post_id}")
        assert delete_response.status_code == 200

        # 6. Verify deletion
        verify_response = await client.get(f"/api/posts/{post_data['slug']}")
        assert verify_response.status_code == 404


@pytest.mark.asyncio
async def test_multilingual_posts(client: AsyncClient, mock_embedding):
    """Test creating and managing posts in multiple languages."""

    posts = [
        {
            "title": "Ollama Tutorial",
            "slug": "ollama-tutorial",
            "content": "Learn how to use Ollama for local AI",
            "language": "en",
            "published": True,
        },
        {
            "title": "Ollama Tutorial",
            "slug": "ollama-tutorial",
            "content": "Lernen Sie, wie Sie Ollama für lokale KI verwenden",
            "language": "de",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            response = await client.post("/api/posts", json=post)
            assert response.status_code == 200

        # Verify both posts exist with same slug but different languages
        en_response = await client.get("/api/posts?lang=en")
        de_response = await client.get("/api/posts?lang=de")

        assert en_response.status_code == 200
        assert de_response.status_code == 200

        en_posts = en_response.json()
        de_posts = de_response.json()

        assert len(en_posts) == 1
        assert len(de_posts) == 1
        assert en_posts[0]["language"] == "en"
        assert de_posts[0]["language"] == "de"


@pytest.mark.asyncio
async def test_similar_posts_workflow(client: AsyncClient, mock_embedding):
    """Test finding similar posts based on content."""

    posts = [
        {
            "title": "Ollama Installation",
            "slug": "ollama-installation",
            "content": "How to install Ollama on your system",
            "language": "en",
            "published": True,
        },
        {
            "title": "Ollama Models",
            "slug": "ollama-models",
            "content": "Available models in Ollama",
            "language": "en",
            "published": True,
        },
        {
            "title": "Docker Basics",
            "slug": "docker-basics",
            "content": "Introduction to Docker containers",
            "language": "en",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post("/api/posts", json=post)

    # Get similar posts for Ollama Installation
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.get("/api/posts/ollama-installation/similar?limit=2")

    assert response.status_code == 200

    similar = response.json()
    assert isinstance(similar, list)
    assert len(similar) <= 2
    # Should not include the original post
    assert all(p["slug"] != "ollama-installation" for p in similar)
