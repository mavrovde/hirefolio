import pytest
from sqlalchemy import select
from app.models.cv_document import CvDocument
from contextlib import asynccontextmanager


@pytest.mark.asyncio

async def test_lifespan_seeds_cv(db_session, init_db):
    # Ensure DB is empty
    result = await db_session.execute(select(CvDocument))
    assert result.scalars().first() is None

    # Trigger lifespan seeding logic manually for testing
    from app.main import lifespan
    from fastapi import FastAPI
    from unittest.mock import patch, MagicMock

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
    with patch("app.main.engine", init_db), \
         patch("app.main.async_session", side_effect=mock_session_cm):
         
        # Mock file system and network calls
        def exists_side_effect(path):
            return str(path).endswith("cv.pdf") or str(path).endswith(".env.local")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("os.path.exists", side_effect=exists_side_effect), \
             patch("builtins.open", new_callable=MagicMock) as mock_open:
            
            mock_get.return_value.status_code = 200
            
            # Mock file read: bytes for PDF, string for env
            def open_side_effect(file, mode="r", *args, **kwargs):
                file_mock = MagicMock()
                if str(file).endswith("cv.pdf") or "rb" in mode:
                    file_mock.__enter__.return_value.read.return_value = b"dummy pdf content"
                else:
                    # For .env files
                    file_mock.__enter__.return_value.read.return_value = "GEMINI_API_KEY=test_key"
                    file_mock.__enter__.return_value.__iter__.return_value = ["GEMINI_API_KEY=test_key"]
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
