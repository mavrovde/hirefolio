from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User


@pytest.mark.asyncio
async def test_lifespan_admin_key_update():
    """
    Test that lifespan startup event updates existing admin key if missing
    and GEMINI_API_KEY_SEED is present.
    """
    # We need to mock the session and user query
    mock_session = AsyncMock()
    mock_user = User(email="admin@example.com", is_admin=True, gemini_api_key=None)

    # Mock result for user query
    # first() call to check if admin exists
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    mock_session.execute.return_value = mock_result

    # Mock result for CV check (so we don't fail later)
    # We can just return None (no CV) or mock it.
    # The code does: cv_result = await session.execute(select(CvDocument))
    # We need to handle the second execute call.
    # We can use side_effect on mock_session.execute

    # Result for CV query
    mock_cv_result = MagicMock()
    mock_cv_result.scalars.return_value.first.return_value = MagicMock()  # CV exists

    mock_session.execute.side_effect = [mock_result, mock_cv_result]

    # Mock get_db context manager (or async_session)
    # app.main uses `async with async_session() as session:`

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    import app.database
    import app.main

    # Patch BOTH locations to be absolutely sure
    with (
        patch.object(app.database, "async_session", mock_factory),
        patch.object(app.main, "async_session", mock_factory),
    ):
        # Mock os.path.exists for .env.local and os.getenv for the key
        with (
            patch("os.path.exists", return_value=True),
            patch("os.getenv", return_value="new-seed-key"),
        ):
            # Trigger lifespan
            from fastapi import FastAPI

            from app.main import lifespan

            app_dummy = FastAPI()

            # Reset mocks to ensure clean state
            mock_session.reset_mock()

            async with lifespan(app_dummy):
                pass

    # Verify user was updated and committed
    assert mock_user.gemini_api_key == "new-seed-key"
    assert mock_session.add.called
    assert mock_session.commit.called
