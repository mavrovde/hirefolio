from app.config import settings
import pytest
from httpx import AsyncClient
from app.models.post import Post


@pytest.mark.asyncio
async def test_get_draft_post_unauthenticated(
    clean_client: AsyncClient, mock_embedding, db_session
):
    """Scenario: Accessing a draft post without admin privileges should return 404."""
    post = Post(
        title="Draft Post",
        slug="draft-post",
        content="Draft content",
        language="en",
        published=False,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    response = await clean_client.get(f"{settings.api_prefix}/posts/{post.id}")
    assert response.status_code == 404

    response = await clean_client.get(f"{settings.api_prefix}/posts/draft-post")
    assert response.status_code == 404
