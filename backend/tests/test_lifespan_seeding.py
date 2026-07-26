from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.models.cv_document import CvDocument
from app.models.user import User


@pytest.mark.asyncio
async def test_lifespan_seeds_cv(db_session, init_db):
    # Ensure DB is empty
    result = await db_session.execute(select(CvDocument))
    assert result.scalars().first() is None

    # Trigger lifespan seeding logic manually for testing
    from unittest.mock import MagicMock, patch

    from fastapi import FastAPI

    from app.main import lifespan

    app = FastAPI()

    # Create a mock session that proxies to our test db_session
    # But lifespan creates a NEW session using async_session() context manager
    # So we need to mock async_session to return a context manager that yields our db_session

    from unittest.mock import AsyncMock

    # Mock the async_session factory to return a Context Manager that yields db_session
    mock_session_factory = MagicMock()

    @asynccontextmanager
    async def mock_session_cm():
        yield db_session

    mock_session_factory.return_value = mock_session_cm()

    # Patch modules
    with (
        patch("app.main.engine", init_db),
        patch("app.main.async_session", side_effect=mock_session_cm),
    ):
        # Mock file system and network calls
        def exists_side_effect(path):
            return str(path).endswith("cv.pdf") or str(path).endswith(".env.local")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
            patch("os.path.exists", side_effect=exists_side_effect),
            patch("builtins.open", new_callable=MagicMock) as mock_open,
        ):
            mock_get.return_value.status_code = 200

            # Mock file read: bytes for PDF, string for env
            def open_side_effect(file, mode="r", *args, **kwargs):
                file_mock = MagicMock()
                if str(file).endswith("cv.pdf") or "rb" in mode:
                    file_mock.__enter__.return_value.read.return_value = (
                        b"dummy pdf content"
                    )
                else:
                    # For .env files
                    file_mock.__enter__.return_value.read.return_value = (
                        "GEMINI_API_KEY=test_key"
                    )
                    file_mock.__enter__.return_value.__iter__.return_value = [
                        "GEMINI_API_KEY=test_key"
                    ]
                return file_mock

            mock_open.side_effect = open_side_effect

            # Execute lifespan
            async with lifespan(app):
                pass

    # Explicitly flush/commit if needed, though lifespan should have committed
    # We query using the same session
    result = await db_session.execute(select(CvDocument))
    seeded_cv = result.scalars().first()

    assert seeded_cv is not None
    assert seeded_cv.filename == "cv.pdf"
    assert seeded_cv.version == "1.0.0-fallback"
    assert seeded_cv.is_active is True


@pytest.mark.asyncio
async def test_lifespan_env_local_without_gemini_key(db_session, init_db, monkeypatch):
    """Covers the `.env.local` present but GEMINI_API_KEY unset/empty branch.

    Pre-seed a user and a CV so the lifespan's admin/CV seeding blocks are no-ops and only
    the env-file loading branch is under test.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    db_session.add(
        User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password="hashed",
            is_admin=True,
            is_active=True,
        )
    )
    db_session.add(
        CvDocument(
            filename="cv.pdf",
            data=b"existing",
            version="existing",
            is_active=True,
        )
    )
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi import FastAPI

    from app.main import lifespan

    app = FastAPI()

    @asynccontextmanager
    async def mock_session_cm():
        yield db_session

    with (
        patch("app.main.engine", init_db),
        patch("app.main.async_session", side_effect=mock_session_cm),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        patch(
            "os.path.exists", side_effect=lambda path: str(path).endswith(".env.local")
        ),
        patch("dotenv.load_dotenv"),
        patch("builtins.open", new_callable=MagicMock),
    ):
        mock_get.return_value.status_code = 200

        async with lifespan(app):
            pass

    # No new user/CV should have been created; existing rows are untouched.
    result = await db_session.execute(select(User))
    assert len(result.scalars().all()) == 1
    result = await db_session.execute(select(CvDocument))
    assert len(result.scalars().all()) == 1
