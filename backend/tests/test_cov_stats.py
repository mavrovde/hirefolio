"""Coverage-focused tests for app.api.stats.get_stats.

These call the endpoint handler directly (in the test's own event loop) so
that coverage can trace the lines that execute *after* each ``await`` on the
async DB session. When the handler is exercised via the ASGI transport the
SQLAlchemy async/greenlet bridge prevents coverage from recording the
post-await resumption lines, even though the code genuinely runs.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.stats import get_stats
from app.models.post import Post


class _FakeUser:
    """Stand-in for the admin user dependency (unused by the handler body)."""

    id = 1
    is_admin = True


async def _seed_posts(db_session: AsyncSession) -> None:
    posts = [
        Post(
            title="Alpha",
            slug="alpha",
            content="c",
            published=True,
            language="en",
            tags=["python", "fastapi"],
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        Post(
            title="Beta",
            slug="beta",
            content="c",
            published=True,
            language="en",
            tags=["python", "testing"],
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        Post(
            title="Gamma",
            slug="gamma",
            content="c",
            published=False,
            language="de",
            tags=["python"],
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_stats_full_body_ai_up(db_session: AsyncSession):
    """Exercise the full happy path with the AI health check succeeding.

    Covers the language grouping, top-tags aggregation, recent-posts
    serialization and the ``ai_status = resp.status_code == 200`` branch.
    """
    await _seed_posts(db_session)

    ok_response = MagicMock()
    ok_response.status_code = 200

    mock_httpx = AsyncMock()
    mock_httpx.get.return_value = ok_response
    mock_httpx.__aenter__.return_value = mock_httpx
    mock_httpx.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        result = await get_stats(db=db_session, current_user=_FakeUser())

    # Post counts (lines 50-55).
    assert result.posts.total == 3
    assert result.posts.published == 2
    assert result.posts.drafts == 1

    # By-language grouping (line 61).
    assert result.posts.by_language["en"] == 2
    assert result.posts.by_language["de"] == 1

    # Top-tags aggregation (lines 67-77).
    assert result.top_tags["python"] == 3
    assert result.top_tags["fastapi"] == 1
    assert result.top_tags["testing"] == 1

    # Recent-posts serialization (lines 81-85), newest first.
    assert [p.slug for p in result.recent_posts] == ["gamma", "beta", "alpha"]
    assert result.recent_posts[0].created_at.startswith("2026-03-01")

    # AI health check success path (lines 91-95).
    assert result.system_health["ai_service"] is True
    assert result.system_health["database"] is True
    mock_httpx.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_stats_ai_down_on_exception(db_session: AsyncSession):
    """When the Ollama probe raises, ai_service falls back to False.

    Covers the ``except Exception`` branch (lines 96-97).
    """
    mock_httpx = AsyncMock()
    mock_httpx.get.side_effect = RuntimeError("connection refused")
    mock_httpx.__aenter__.return_value = mock_httpx
    mock_httpx.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        result = await get_stats(db=db_session, current_user=_FakeUser())

    # Empty DB: aggregations return empty collections without error.
    assert result.posts.total == 0
    assert result.posts.by_language == {}
    assert result.top_tags == {}
    assert result.recent_posts == []
    assert result.system_health["ai_service"] is False
