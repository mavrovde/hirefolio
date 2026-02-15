import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

# Prefix is likely /api/v1 or similar
API_PREFIX = settings.api_prefix

@pytest.mark.asyncio
async def test_upload_and_get_post_image(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_token_headers: dict,
):
    # 1. Create a post
    post_data = {
        "title": "Image Test Post",
        "slug": "image-test-post",
        "content": "Content for image test",
        "language": "en",
        "published": True
    }
    response = await async_client.post(f"{API_PREFIX}/posts", json=post_data, headers=admin_token_headers)
    assert response.status_code == 200, f"Failed to create post: {response.text}"
    post_id = response.json()["id"]

    # 2. Upload an image
    # Create a dummy image (1x1 pixel transparent gif)
    fake_image_content = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
    
    files = {"file": ("test_image.gif", fake_image_content, "image/gif")}
    
    response = await async_client.put(f"{API_PREFIX}/posts/{post_id}/image", files=files, headers=admin_token_headers)
    assert response.status_code == 200, f"Failed to upload image: {response.text}"
    data = response.json()
    
    # 3. Verify post response contains image_url pointing to API
    # Should point to /api/posts/{id}/image (or whatever prefix is)
    expected_url = f"{API_PREFIX}/posts/{post_id}/image"
    assert data["image_url"] == expected_url, f"Expected {expected_url}, got {data.get('image_url')}"
    
    # 4. Get the image
    response = await async_client.get(expected_url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
    assert response.content == fake_image_content

@pytest.mark.asyncio
async def test_upload_image_post_not_found(
    async_client: AsyncClient,
    admin_token_headers: dict,
):
    files = {"file": ("test.jpg", b"fake", "image/jpeg")}
    response = await async_client.put(f"{API_PREFIX}/posts/999999/image", files=files, headers=admin_token_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_image_not_found(
    async_client: AsyncClient,
):
    response = await async_client.get(f"{API_PREFIX}/posts/999999/image")
    assert response.status_code == 404
