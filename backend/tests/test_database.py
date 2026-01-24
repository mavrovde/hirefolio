import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """Test that get_db yields a valid session."""
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        assert session is not None


@pytest.mark.asyncio
async def test_db_session_fixture(db_session):
    """Test that the db_session fixture provides a valid session."""
    assert isinstance(db_session, AsyncSession)
    assert db_session.is_active
