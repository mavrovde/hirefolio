import pytest
from httpx import AsyncClient

# Tests for posts.py coverage
# Missing lines: 29-31, 45-47, 126-175, 203-214, 235-246, 268-286, 307-333, 356-428, 447-452, 460-463, 481-533, 555-585, 606-615


@pytest.mark.asyncio
async def test_posts_validation_error(client: AsyncClient):
    # Test tags validation error (lines 26-31, 42-47)
    # Create post with > 5 tags
    response = await client.post(
        "/api/app/posts",
        json={
            "title": "Test",
            "slug": "test",
            "content": "Content",
            "tags": ["1", "2", "3", "4", "5", "6"],
        },
    )
    assert response.status_code == 422
    assert "Max 5 tags allowed" in str(response.json())
