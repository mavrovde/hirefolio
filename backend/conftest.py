import sys
from unittest.mock import MagicMock

# Global mocks for dependencies that require Rust/tiktoken or other system deps
# Must be before any 'app' imports which might trigger nested imports of these
mock_crewai = MagicMock()
sys.modules["crewai"] = mock_crewai
mock_crewai.Agent = MagicMock
mock_crewai.Task = MagicMock
mock_crewai.Crew = MagicMock
# Process needs .sequential attribute
mock_process = MagicMock()
mock_process.sequential = "sequential"
mock_crewai.Process = mock_process

mock_lc = MagicMock()
sys.modules["langchain_community"] = mock_lc
sys.modules["langchain_community.chat_models"] = mock_lc
mock_lc.ChatOllama = MagicMock

from typing import AsyncGenerator  # noqa: E402
import pytest  # noqa: E402
from httpx import AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402
import os  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

# Test database URL
DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or settings.database_url
).replace("localhost", "127.0.0.1")

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


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test using a clean slate strategy."""
    # 1. Reset Database State (Brute force stability to avoid DBAPIError)
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 2. Provide a new session
    async with test_async_session() as session:
        yield session
        await session.close()


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
    """Return a mock embedding vector (768 dimensions)."""
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
