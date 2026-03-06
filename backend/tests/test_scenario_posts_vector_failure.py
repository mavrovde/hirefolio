import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

# Scenario: Vector database search fails (e.g. timeout, connection error)
# Expected: System gracefully falls back to keyword search and returns results (or empty list if none) without crashing.


@pytest.mark.asyncio
async def test_posts_scenario_vector_search_failure_fallback(client: AsyncClient):
    # Overwrite get_embedding to ensure vector search path is taken
    # get_embedding is async, so we need AsyncMock or explicit awaitable return
    from unittest.mock import AsyncMock

    with patch(
        "app.api.posts.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 768
    ):
        # Patch db.execute to Simulate Vector Failure then Keyword Success
        # The code calls `await db.execute(vector_query)` then `await db.execute(keyword_query)`

        # Create a mock result for the keyword search (2nd call)
        mock_keyword_result = MagicMock()
        mock_keyword_result.scalars.return_value.all.return_value = []  # Empty results
        mock_keyword_result.all.return_value = []

        # Helper to make a mock awaitable by setting __await__ or just wrapping in async function
        async def side_effect(*args, **kwargs):
            print(f"DEBUG: db.execute called with args: {args}")
            # First call (vector search) might be identified by query or order.
            state = side_effect.state
            side_effect.state += 1
            if state == 0:
                raise ValueError("Vector DB Connection Fail")
            return mock_keyword_result

        side_effect.state = 0

        # Setup side_effect: First call raises, second returns mock (via awaitable)

        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=side_effect
        ):
            print("DEBUG: Test - calling semantic search")
            response = await client.get("/api/app/posts/search/semantic?q=test_query")
            print(f"DEBUG: Test - response status {response.status_code}")

            assert response.status_code == 200
            # It should return a list (empty in this case), not 500
            assert response.json() == []


# Scenario: External AI service for post generation returns None (unexpected failure)
# Expected: 500 Internal Server Error with specific message


@pytest.mark.asyncio
async def test_posts_scenario_generation_service_returns_none(client: AsyncClient):
    # But this is an external fixture. We can import or re-declare.
    # Better to use the one from conftest or `fixtures_auth_custom` if implicitly available.
    # We will assume we can get it if we define it in args? No, need to import.
    pass

    # Actually, we can just patch dependency or use client with auth.
    # Let's rely on standard client logic if we can mock valid token.
    # Or just import the token creation logic.

    # Easier: Just mock `get_current_admin_user` dependency?
    # Yes, that avoids token logic entirely.

    user_mock = MagicMock()
    user_mock.is_admin = True
    user_mock.gemini_api_key = "fake_key"

    with patch("app.api.posts.get_current_admin_user", return_value=user_mock):
        with patch("app.services.ai.generate_full_post", return_value=None):
            response = await client.post(
                "/api/app/posts/generate", json={"topic": "fail"}
            )
            assert response.status_code == 500
            assert "Failed to generate" in response.json()["detail"]
