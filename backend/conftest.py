import sys
from unittest.mock import MagicMock

# Global mocks for dependencies that require Rust/tiktoken or other system deps
# Must be before any 'app' imports which might trigger nested imports of these

# Langchain and other external mocks
def mock_module(name):
    # Use a fresh MagicMock for each module to avoid shared side_effect exhaustion
    m = MagicMock()
    m.__name__ = name
    sys.modules[name] = m
    return m

mock_module("tiktoken")
mock_module("langchain")
mock_module("langchain_core")
mock_module("langchain_core.messages")
mock_module("langchain_core.prompts")
mock_module("langchain_core.output_parsers")
mock_module("langchain_core.runnables")
mock_module("langchain_google_genai")
mock_module("langchain_openai")
mock_module("langchain_anthropic")
mock_module("langchain_community")

# Mock heavy/problematic libs
mock_numpy = mock_module("numpy")
mock_numpy.ndarray = MagicMock

# Create a mock that looks like a SQLAlchemy TypeEngine
from sqlalchemy.types import UserDefinedType  # noqa: E402
from sqlalchemy.sql import expression  # noqa: E402

class MockVector(UserDefinedType):
    def __init__(self, dim=None):
        self.dim = dim
    
    def get_col_spec(self, **kw):
        return "VECTOR"
        
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            # Convert list/array to string format "[1.0, 2.0, ...]" for postgres
            return str(list(value))
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                # asyncpg might return the vector as a string if types aren't registered
                # format is usually "[0.1,0.2,...]"
                import json
                try:
                    return json.loads(value)
                except Exception:
                    # Fallback for simple parsing if json fails (postgres format)
                    return [float(x) for x in value.strip("[]").split(",")]
            return value
        return process
        
    class Comparator(UserDefinedType.Comparator):
        def cosine_distance(self, other):
            return expression.literal_column("0.5") # Mock distance

    comparator_factory = Comparator

mock_pgvector = mock_module("pgvector")
mock_pgvector_sqla = mock_module("pgvector.sqlalchemy")
mock_pgvector_sqla.Vector = MockVector

# Special handling for classes that are inherited from
mock_lc_callbacks = mock_module("langchain_core.callbacks")
class BaseCallbackHandler:
    pass
mock_lc_callbacks.BaseCallbackHandler = BaseCallbackHandler

mock_lc_comm_chat = mock_module("langchain_community.chat_models")
mock_lc_comm_chat.ChatOllama = MagicMock

mock_lc_tools = mock_module("langchain.tools")
class BaseToolMock:
    name: str = ""
    description: str = ""
    def __init__(self, *args, **kwargs): pass
mock_lc_tools.BaseTool = BaseToolMock

# CrewAI mocks
mock_crewai = mock_module("crewai")
class MockProcess:
    sequential = "sequential"
    hierarchical = "hierarchical"
mock_crewai.Process = MockProcess
mock_crewai.Agent = MagicMock
mock_crewai.Task = MagicMock
mock_crewai.Crew = MagicMock

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
async def init_db():
    """Initialize the database schema for each test."""
    from app.database import Base
    engine = get_test_engine()

    # Reset Database State
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture(scope="function")
async def db_session(init_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test using a clean slate strategy."""
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

    # Patch app.database.async_session to use test sessionmaker
    # This ensures lifespan events use the TEST database, avoiding InvalidRequestError
    # and isolation issues.
    from unittest.mock import patch
    
    # We need to catch where it is imported in main.py
    # app.main imports async_session from app.database
    # So we patch app.database.async_session BEFORE app startup
    
    test_session_maker = get_test_async_session()
    
    # We patch 'app.main.async_session' because that's where lifespan uses it
    p = patch("app.main.async_session", side_effect=test_session_maker)
    p.start()

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
    p.stop()


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




@pytest.fixture(scope="function")
async def clean_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client WITHOUT admin auth overrides.
    
    Used for testing permission denied scenarios where we need real auth checks.
    """
    from app.main import app
    from app.database import get_db
    from unittest.mock import patch
    from datetime import datetime, timezone

    if not hasattr(app.state, "start_time") or app.state.start_time is None:
        app.state.start_time = datetime.now(timezone.utc)

    test_session_maker = get_test_async_session()
    p = patch("app.main.async_session", side_effect=test_session_maker)
    p.start()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    p.stop()


@pytest.fixture
def admin_token_headers():
    """Return Authorization headers for admin user.
    
    Auth is already overridden in the client fixture, so any Bearer token works.
    """
    return {"Authorization": "Bearer test-admin-token"}


@pytest.fixture
def normal_user_token_headers():
    """Return Authorization headers for a non-admin user."""
    return {"Authorization": "Bearer non-admin-token"}

