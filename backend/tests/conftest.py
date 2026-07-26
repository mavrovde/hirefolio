from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app


@pytest.fixture(scope="function")
async def clean_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client WITHOUT auth overrides."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_embedding():
    """Return a mock embedding vector (list of floats)."""
    return [0.1] * 768


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Reset in-memory rate-limiter state before and after every test.

    The limiters hold module-level state keyed by client IP; without this,
    request counts from one test would bleed into the next (all httpx
    ASGI-transport test requests share the same synthetic client IP), making
    tests order-dependent.
    """
    from app.services.rate_limit import reset_all_rate_limiters

    reset_all_rate_limiters()
    yield
    reset_all_rate_limiters()


@pytest.fixture(autouse=True)
def mock_embedding_global(mocker):
    """Global mock for embeddings to prevent external API calls during tests."""
    val = [0.1] * 768

    async def mock_get_embedding(*args, **kwargs):
        return val[:]

    # Patch the service and api imports
    mocker.patch(
        "app.services.embeddings.get_embedding", side_effect=mock_get_embedding
    )
    mocker.patch("app.api.posts.get_embedding", side_effect=mock_get_embedding)
    mocker.patch("app.api.linkedin.get_embedding", side_effect=mock_get_embedding)

    return mock_get_embedding
