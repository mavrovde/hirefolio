import logging
import os
import sys
import tempfile
from unittest.mock import MagicMock

# The LinkedIn session directory defaults to a persistent, mounted volume
# (/data/linkedin_cookies) that isn't writable on dev/CI machines. Point it at a
# writable temp dir for the test run before any 'app' import instantiates the
# settings / LinkedInService (which os.makedirs the directory at import time).
os.environ.setdefault(
    "LINKEDIN_COOKIES_DIR",
    os.path.join(tempfile.gettempdir(), "linkedin_cookies_test"),
)

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
from sqlalchemy.sql import expression
from sqlalchemy.types import UserDefinedType


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
            return expression.literal_column("0.5")  # Mock distance

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

mock_lc_tools = mock_module("langchain_core.tools")


class BaseToolMock:
    name: str = ""
    description: str = ""

    def __init__(self, *args, **kwargs):
        pass


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

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Defer initialization of engine and sessionmaker to avoid early imports
_test_engine = None
_test_async_session = None


def _base_test_url() -> str:
    """Return the configured (single, shared) test database URL.

    Resolution order mirrors the project convention: ``TEST_DATABASE_URL`` →
    ``DATABASE_URL`` → the app's configured ``database_url``. ``localhost`` is
    normalized to ``127.0.0.1`` to avoid IPv6/socket ambiguity on CI/dev.
    """
    from app.config import settings

    return (
        os.getenv("TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or settings.database_url
    ).replace("localhost", "127.0.0.1")


def _xdist_worker_id() -> str | None:
    """Return the ``pytest-xdist`` worker id (``gw0``, ``gw1``, …).

    Returns ``None`` when tests run serially (no ``-n``) or on the xdist
    controller (``master``), so the original single-database behavior is
    preserved verbatim in that case.
    """
    worker = os.getenv("PYTEST_XDIST_WORKER")
    if not worker or worker == "master":
        return None
    return worker


def _test_database_url() -> URL:
    """Return the effective test DB URL, isolated per xdist worker.

    Under ``pytest-xdist`` every worker gets its own database
    (``<db>_<worker>``) so parallel workers never collide on shared rows or
    unique constraints (e.g. ``ux_post_slug_lang`` / ``ix_post_source_urn``).
    Without xdist the single shared database is used unchanged.
    """
    url = make_url(_base_test_url())
    worker = _xdist_worker_id()
    if worker is not None:
        url = url.set(database=f"{url.database}_{worker}")
    return url


async def _create_database_if_missing(url: URL) -> None:
    """Create ``url``'s database on the server if it does not yet exist.

    Connects to the ``postgres`` maintenance database (``CREATE DATABASE`` can't
    run inside a transaction / against the target DB itself) via asyncpg, using
    the same host/port/credentials as the target URL.
    """
    import asyncpg

    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", url.database
        )
        if not exists:
            # Identifier is derived from our own config + the xdist worker id
            # (never user input), so quoting it directly is safe here.
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _drop_database(url: URL) -> None:
    """Drop ``url``'s database (best-effort session cleanup for xdist workers)."""
    import asyncpg

    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        # WITH (FORCE) terminates any lingering backend so the drop can't hang
        # on a stray connection at teardown (PostgreSQL 13+).
        await conn.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
    finally:
        await conn.close()


def pytest_configure(config):
    """Ensure this process's test database exists before collection/tests run.

    Runs once per process — on the xdist controller (shared DB) and in each
    worker subprocess (its own ``<db>_<worker>``). ``PYTEST_XDIST_WORKER`` is
    already set in the worker environment at this point, so each worker
    provisions its own isolated database.
    """
    asyncio.run(_create_database_if_missing(_test_database_url()))


def pytest_unconfigure(config):
    """Drop this worker's ephemeral database at session end (xdist only).

    The shared single database (serial runs / controller) is intentionally left
    intact; only per-worker throwaway DBs are cleaned up. Cleanup is
    best-effort: a teardown failure must never fail an otherwise-green run.
    """
    if _xdist_worker_id() is None:
        return
    try:
        asyncio.run(_drop_database(_test_database_url()))
    except Exception as exc:  # pragma: no cover - best-effort teardown only
        # Never fail an otherwise-green run on cleanup; surface it as a warning.
        logging.getLogger(__name__).warning("test DB cleanup failed: %s", exc)


def get_test_engine():
    global _test_engine
    if _test_engine is None:
        _test_engine = create_async_engine(
            _test_database_url(), poolclass=NullPool, echo=False
        )
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
    from datetime import datetime

    from app.database import get_db
    from app.main import app
    from app.models.user import User
    from app.services.auth import (
        get_current_admin_user,
        get_current_user,
        get_current_user_optional,
        get_password_hash,
    )

    # Ensure app state is initialized for stats tests
    if not hasattr(app.state, "start_time") or app.state.start_time is None:
        app.state.start_time = datetime.now(UTC)

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


@pytest.fixture(scope="function")
async def normal_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client overridden with a normal (non-admin) user."""
    from datetime import datetime
    from unittest.mock import patch

    from app.database import get_db
    from app.main import app
    from app.models.user import User
    from app.services.auth import (
        get_current_user,
        get_current_user_optional,
        get_password_hash,
    )

    if not hasattr(app.state, "start_time") or app.state.start_time is None:
        app.state.start_time = datetime.now(UTC)

    test_session_maker = get_test_async_session()
    p = patch("app.main.async_session", side_effect=test_session_maker)
    p.start()

    async def override_get_db():
        yield db_session

    mock_user = User(
        id=2,
        username="normaluser",
        email="user@example.com",
        hashed_password=get_password_hash("userpass"),
        is_admin=False,
        is_active=True,
    )

    async def override_auth():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
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
    from datetime import datetime
    from unittest.mock import patch

    from app.database import get_db
    from app.main import app

    if not hasattr(app.state, "start_time") or app.state.start_time is None:
        app.state.start_time = datetime.now(UTC)

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
