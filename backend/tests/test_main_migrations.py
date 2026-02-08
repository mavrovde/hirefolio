import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import lifespan
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_main_migrations_trigger():
    """Test the migration logic in app.main.lifespan."""
    app = FastAPI()

    # Mock engine.begin() and engine.connect()
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = []
    mock_conn.execute.return_value = mock_result

    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    # We only need to mock begin() since lifespan ONLY uses engine.begin()
    mock_engine.begin.return_value = mock_cm
    # connect is not used in the snippet I saw, but if it is, mock it too safely
    mock_engine.connect.return_value = mock_cm

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.async_session") as mock_session_factory,
    ):
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_session.execute.return_value = mock_execute_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # Mock user and CV queries to avoid errors
        mock_execute_result.scalars.return_value.first.return_value = MagicMock()

        # We also need to mock the CV seeding part to avoid file system issues
        # and search for specific columns
        mock_conn.execute.return_value = MagicMock(__iter__=lambda x: iter([]))

        with patch("os.path.exists", return_value=False):
            # Trigger lifespan
            async with lifespan(app):
                pass

    # Verify ALTER TABLE was called
    calls = mock_conn.execute.call_args_list

    def get_sql(call):
        args = call[0]
        if args and hasattr(args[0], "text"):
            return args[0].text
        return str(args[0])

    assert any("ALTER TABLE cv_requests" in get_sql(call) for call in calls)


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

            with patch("app.main.engine") as mock_engine:
                # Mock engine to avoid migration logic failure
                mock_conn = AsyncMock()
                mock_result_migrate = MagicMock()
                mock_result_migrate.__iter__.return_value = [
                    ("downloaded_at",),
                    ("download_count",),
                    ("position_description",),
                    ("subscribe_to_updates",),
                ]
                mock_conn.execute.return_value = mock_result_migrate

                async def mock_aenter(*args, **kwargs):
                    return mock_conn

                async def mock_aexit(*args, **kwargs):
                    pass

                # Mock begin() since lifespan uses it
                mock_engine.begin.return_value.__aenter__ = mock_aenter
                mock_engine.begin.return_value.__aexit__ = mock_aexit

                async with lifespan(app):
                    pass


@pytest.mark.asyncio
async def test_main_migrations_column_exists():
    """Test migration skip path when columns already exist."""
    app = FastAPI()
    
    # Use simpler mocking to avoid loop issues
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = [
        ("downloaded_at",), 
        ("download_count",), 
        ("position_description",),
        ("subscribe_to_updates",)
    ]
    mock_conn.execute.return_value = mock_result

    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin.return_value = mock_cm

    # Mock session factory and session
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    # Ensure seeding queries don't fail
    mock_session.execute.return_value = MagicMock()

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.async_session", mock_session_factory),
        patch("os.path.exists", return_value=False)
    ):
        async with lifespan(app):
            pass

    # Verify no ALTER TABLE was called
    calls = mock_conn.execute.call_args_list
    def get_sql(call):
        args = call[0]
        return args[0].text if hasattr(args[0], "text") else str(args[0])

    assert not any("ALTER TABLE" in get_sql(call) for call in calls)


@pytest.mark.asyncio
async def test_main_migrations_exception():
    """Test the exception handling in migration logic."""
    app = FastAPI()

    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(side_effect=Exception("Migration Failed"))
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin.return_value = mock_cm

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.async_session") as mock_session_factory,
    ):
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_session.execute.return_value = mock_execute_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_execute_result.scalars.return_value.first.return_value = MagicMock()

        with patch("os.path.exists", return_value=False):
            async with lifespan(app):
                pass

    mock_engine.begin.assert_called()
