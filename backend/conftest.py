import asyncio
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app


import os

from app.config import settings

# Test database URL - prioritize TEST_DATABASE_URL (local), then DATABASE_URL (CI), then fallback
DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or settings.database_url
)

# Create test engine
test_engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

test_async_session = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with test_async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database and auth dependencies."""

    from app.services.auth import (
        get_current_admin_user,
        get_current_user_optional,
        get_current_user,
    )
    from app.models.user import User

    async def override_get_db():
        yield db_session

    mock_admin = User(
        id=1, username="admin", email="admin@example.com", is_admin=True, is_active=True
    )

    async def override_auth():
        return mock_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin_user] = override_auth
    app.dependency_overrides[get_current_user_optional] = override_auth
    app.dependency_overrides[get_current_user] = override_auth

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_embedding():
    """Return a mock embedding vector (768 dimensions for nomic-embed-text)."""
    return [0.1] * 768


@pytest.fixture
def sample_post_data():
    """Return sample post data for testing."""
    return {
        "title": "Test Post",
        "slug": "test-post",
        "content": "This is a test post content.",
        "summary": "Test summary",
        "language": "en",
        "published": True,
    }
