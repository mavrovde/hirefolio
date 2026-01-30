import pytest
from sqlalchemy import select
from app.models.cv_document import CvDocument


@pytest.mark.asyncio
async def test_lifespan_seeds_cv(db_session):
    # Ensure DB is empty
    result = await db_session.execute(select(CvDocument))
    assert result.scalars().first() is None

    # Trigger lifespan seeding logic manually for testing
    from app.main import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    # We need to simulate the lifespan context
    async with lifespan(app):
        # The lifespan context manager handles the session internally if we look at main.py
        # But wait, main.py uses async_session() which is a factory.
        pass

    # Check if CV was seeded
    result = await db_session.execute(select(CvDocument))
    seeded_cv = result.scalars().first()

    assert seeded_cv is not None
    assert seeded_cv.filename == "cv.pdf"
    assert seeded_cv.version == "1.0.0-fallback"
    assert seeded_cv.is_active is True
