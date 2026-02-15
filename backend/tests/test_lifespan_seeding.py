import pytest
from sqlalchemy import select
from app.models.cv_document import CvDocument


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
    
    # Create a mock session maker that yields our existing test session
    # We need an async context manager
    class MockSessionContext:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    mock_session_maker = MagicMock(return_value=MockSessionContext())

    # Mock engine.begin() to return a context manager that yields a connection
    # We can probably use the existing DB session's bind (connection) or just mock it to do nothing
    # if we only care about the session part.
    # However, lifespan also does `async with engine.begin() as conn:` for migrations.
    # We should point it to the test engine.
    
    # Patch app.main.engine and app.main.async_session
    with patch("app.main.engine", init_db), \
         patch("app.main.async_session", mock_session_maker):
         
        # We also need to mock ollama check to avoid network calls/timeouts
        with patch("httpx.AsyncClient.get", new_callable=MagicMock) as mock_get:
            mock_get.return_value.status_code = 200
            
            # We need to simulate the lifespan context
            async with lifespan(app):
                pass

    # Check if CV was seeded
    # The session we passed to lifespan (db_session) should have the changes
    # But wait, did lifespan commit? 
    # Yes, `await session.commit()` in lifespan.
    # Since db_session fixture usually runs in a transaction that rolls back, 
    # committing inside might be tricky if using `nested` transaction or `savepoint`.
    # But our `db_session` fixture (in conftest) yields a session made from `get_test_engine`.
    # It closes at the end.
    
    # We need to verify the data is there.
    # Since we reused the same session, we might need to expire/refresh if we want to see changes 
    # made "by the app" reflected in our view, but it's the SAME session object.
    
    result = await db_session.execute(select(CvDocument))
    seeded_cv = result.scalars().first()

    assert seeded_cv is not None
    assert seeded_cv.filename == "cv.pdf"
    assert seeded_cv.version == "1.0.0-fallback"
    assert seeded_cv.is_active is True
