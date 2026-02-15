import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

# Scenario: Creating a post with a slug that already exists
# Expected: System detects collision, retries with a modified slug, and succeeds.

@pytest.mark.asyncio
async def test_posts_scenario_slug_collision_auto_retry(client: AsyncClient):
    # Mock admin user
    user_mock = MagicMock()
    user_mock.is_admin = True
    
    # We need to control the DB interaction precisely.
    # The code:
    # try: 
    #   db.add(post); await db.commit()
    # except:
    #   await db.rollback()
    #   modify slug
    #   db.add(post); await db.commit()
    
    # We patch `AsyncSession.commit`.
    
    commit_calls = 0
    async def side_effect_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            raise Exception("IntegrityError: Duplicate Key")
        return None

    with patch("app.api.posts.get_current_admin_user", return_value=user_mock):
        with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=side_effect_commit):
            # Use AsyncMock for async methods
            with patch("sqlalchemy.ext.asyncio.AsyncSession.rollback", new_callable=MagicMock) as mock_rollback:
                 mock_rollback.return_value.__aenter__ = MagicMock(return_value=None) # Hack for context? No, just awaitable.
                 # AsyncMock is available in unittest.mock in Python 3.8+
                 pass 
            
            # Better way: just patch with a coroutine or AsyncMock
            from unittest.mock import AsyncMock
            from datetime import datetime
            
            async def side_effect_refresh(instance, *args, **kwargs):
                instance.id = 1
                instance.created_at = datetime.now()
                instance.updated_at = datetime.now()
                return None

            refresh_mock = AsyncMock(side_effect=side_effect_refresh)
            
            with patch("sqlalchemy.ext.asyncio.AsyncSession.rollback", new_callable=AsyncMock), \
                 patch("sqlalchemy.ext.asyncio.AsyncSession.refresh", new_callable=AsyncMock, side_effect=side_effect_refresh):
                 
                 response = await client.post("/api/app/posts", json={
                    "title": "Slug Collision Post", "slug": "col-slug", "content": "content"
                })
                 
                 assert response.status_code == 200
                 # Verify slug was changed
                 slug = response.json().get("slug")
                 assert slug != "col-slug"
                 assert slug.startswith("col-slug-")
