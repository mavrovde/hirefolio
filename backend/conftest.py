import sys
from unittest.mock import MagicMock

# Global mocks for dependencies that require Rust/tiktoken or other system deps
# Must be before any 'app' imports which might trigger nested imports of these
from types import SimpleNamespace  # noqa: E402


# CrewAI mocks
class MockProcess:
    sequential = "sequential"
    hierarchical = "hierarchical"


mock_crewai = SimpleNamespace(
    Process=MockProcess, Agent=MagicMock, Task=MagicMock, Crew=MagicMock
)
sys.modules["crewai"] = mock_crewai

mock_lc = MagicMock()
sys.modules["langchain_community"] = mock_lc
sys.modules["langchain_community.chat_models"] = mock_lc
mock_lc.ChatOllama = MagicMock

# Additional mocks for langchain-openai and others
mock_lc_tools = MagicMock()
class BaseToolMock(MagicMock):
    pass
mock_lc_tools.BaseTool = BaseToolMock
sys.modules["langchain.tools"] = mock_lc_tools

sys.modules["langchain"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["tiktoken"] = MagicMock()

from typing import AsyncGenerator  # noqa: E402
import pytest  # noqa: E402
from httpx import AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402
import os  # noqa: E402

# Defer initialization of engine and sessionmaker to avoid early imports
_test_engine = None
_test_async_session = None


def get_test_engine():
    global _test_engine
    if _test_engine is None:
        from app.config import settings

        url = (
            os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or settings.database_url
        ).replace("localhost", "127.0.0.1")
        _test_engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return _test_engine


def get_test_async_session():
    global _test_async_session
    if _test_async_session is None:
        _test_async_session = async_sessionmaker(
            get_test_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _test_async_session


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test using a clean slate strategy."""
    from app.database import Base

    engine = get_test_engine()

    # 1. Reset Database State (Brute force stability to avoid DBAPIError)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 2. Provide a new session
    sessionmaker = get_test_async_session()
    async with sessionmaker() as session:
        yield session
        await session.close()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database and auth dependencies."""
    from app.main import app
    from app.database import get_db
    from app.services.auth import (
        get_current_admin_user,
        get_current_user_optional,
        get_current_user,
        get_password_hash,
    )
    from app.models.user import User
    from datetime import datetime, timezone

    # Ensure app state is initialized for stats tests
    if not hasattr(app.state, "start_time") or app.state.start_time is None:
        app.state.start_time = datetime.now(timezone.utc)
    app.version = "1.2.3-test"

    async def override_get_db():
        yield db_session

    mock_admin = User(
        id=1,
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin"),
        is_admin=True,
        is_active=True,
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
