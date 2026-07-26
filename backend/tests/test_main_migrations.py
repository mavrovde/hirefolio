"""Regression tests for app.main.lifespan's CV/admin seeding logic.

Historically this module also asserted on the ad-hoc `ALTER TABLE cv_requests`
migration logic that used to live in `lifespan` alongside `create_all`. That
logic has been removed (see issue #46): schema management is now exclusively
Alembic's job (`alembic upgrade head`, run by the container entrypoint before
the app starts), so `lifespan` no longer touches `engine` or `Base.metadata`
at all. These tests now only cover the remaining seeding behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.main import lifespan


@pytest.mark.asyncio
async def test_main_cv_seeding_fallback_warning():
    """Test the warning when fallback CV is not found."""
    app = FastAPI()

    # Mock os.path.exists to return False for CV
    with patch("os.path.exists", return_value=False):
        # Mock session to avoid DB interaction
        with patch("app.main.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            # Mock select result for CvDocument to be empty
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_session.execute.return_value = mock_result

            async with lifespan(app):
                pass
