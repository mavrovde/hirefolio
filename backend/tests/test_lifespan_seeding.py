from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import settings as app_settings
from app.models.cv_document import CvDocument
from app.models.user import User
from app.services.auth import get_password_hash, verify_password


async def _run_seed_lifespan(db_session):
    """Drive the lifespan seed against ``db_session`` with the filesystem/network
    isolated (no ``.env.local``, no fallback ``cv.pdf``, Ollama check stubbed)."""
    from fastapi import FastAPI

    from app.main import lifespan

    app = FastAPI()

    @asynccontextmanager
    async def mock_session_cm():
        yield db_session

    with (
        patch("app.main.async_session", side_effect=mock_session_cm),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        patch("os.path.exists", return_value=False),
    ):
        mock_get.return_value.status_code = 200
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_seeds_admin_with_admin_password(
    db_session, init_db, monkeypatch
):
    """Issue #142 (a): with ADMIN_PASSWORD set, the seeded admin uses it."""
    monkeypatch.setattr(app_settings, "admin_password", "S3cret-Pw!")

    await _run_seed_lifespan(db_session)

    result = await db_session.execute(select(User))
    admins = result.scalars().all()
    assert len(admins) == 1
    admin = admins[0]
    assert admin.username == "admin"
    assert admin.is_admin is True
    # Password is the configured ADMIN_PASSWORD, NOT the historical weak default.
    assert verify_password("S3cret-Pw!", admin.hashed_password) is True
    assert verify_password("admin", admin.hashed_password) is False


@pytest.mark.asyncio
async def test_lifespan_refuses_weak_default_admin_without_admin_password(
    db_session, init_db, monkeypatch
):
    """Issue #142 (b): prod path refuses to seed a weak-default admin.

    With no users present and ADMIN_PASSWORD unset, the seed must NOT create a
    login-able ``admin`` account (so prod never ships ``admin``/``admin``).
    """
    monkeypatch.setattr(app_settings, "admin_password", "")

    await _run_seed_lifespan(db_session)

    result = await db_session.execute(select(User))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_e2e_seed_creates_admin_regardless_of_admin_password(
    db_session, init_db, monkeypatch
):
    """Issue #142 (c): the test/dev (E2E) seed still provisions an admin.

    ``scripts/seed_e2e_user.py`` keeps its own throwaway credentials and must
    keep working even when ADMIN_PASSWORD is unset (it is the sanctioned
    local/E2E path that does not depend on the prod seed refusal).
    """
    monkeypatch.setattr(app_settings, "admin_password", "")

    import scripts.seed_e2e_user as seed_e2e

    @asynccontextmanager
    async def mock_session_cm():
        yield db_session

    with patch.object(seed_e2e, "async_session", side_effect=mock_session_cm):
        await seed_e2e.seed_e2e_user()

    result = await db_session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one()
    assert admin.is_admin is True
    assert verify_password("admin123", admin.hashed_password) is True


@pytest.mark.asyncio
async def test_lifespan_rotates_existing_weak_default_admin(
    db_session, init_db, monkeypatch
):
    """Issue #142 rotation: an existing admin still on the weak ``admin`` default
    is rotated to ADMIN_PASSWORD automatically on startup.

    This closes the LIVE vuln on the long-lived prod DB (where the ``if not
    user`` seed never runs) without a manual step.
    """
    monkeypatch.setattr(app_settings, "admin_password", "Rotated-Pw!")
    db_session.add(
        User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password=get_password_hash("admin"),
            is_admin=True,
            is_active=True,
        )
    )
    await db_session.commit()

    await _run_seed_lifespan(db_session)

    result = await db_session.execute(select(User))
    admin = result.scalar_one()
    assert verify_password("Rotated-Pw!", admin.hashed_password) is True
    # The old weak default no longer works.
    assert verify_password("admin", admin.hashed_password) is False


@pytest.mark.asyncio
async def test_lifespan_does_not_clobber_custom_admin_password(
    db_session, init_db, monkeypatch
):
    """Issue #142 rotation guard: an admin whose password was legitimately
    changed (no longer the weak default) is NOT overwritten by startup, even
    when ADMIN_PASSWORD is set to something else.
    """
    monkeypatch.setattr(app_settings, "admin_password", "Rotated-Pw!")
    db_session.add(
        User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password=get_password_hash("operator-set-strong-pw"),
            is_admin=True,
            is_active=True,
        )
    )
    await db_session.commit()

    await _run_seed_lifespan(db_session)

    result = await db_session.execute(select(User))
    admin = result.scalar_one()
    # Custom password preserved; ADMIN_PASSWORD did NOT overwrite it.
    assert verify_password("operator-set-strong-pw", admin.hashed_password) is True
    assert verify_password("Rotated-Pw!", admin.hashed_password) is False


@pytest.mark.asyncio
async def test_lifespan_seeds_cv(db_session, init_db):
    # Ensure DB is empty
    result = await db_session.execute(select(CvDocument))
    assert result.scalars().first() is None

    # Trigger lifespan seeding logic manually for testing
    from unittest.mock import MagicMock, patch

    from fastapi import FastAPI

    from app.main import lifespan

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
    with patch("app.main.async_session", side_effect=mock_session_cm):
        # Mock file system and network calls
        def exists_side_effect(path):
            return str(path).endswith("cv.pdf") or str(path).endswith(".env.local")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
            patch("os.path.exists", side_effect=exists_side_effect),
            patch("builtins.open", new_callable=MagicMock) as mock_open,
        ):
            mock_get.return_value.status_code = 200

            # Mock file read: bytes for PDF, string for env
            def open_side_effect(file, mode="r", *args, **kwargs):
                file_mock = MagicMock()
                if str(file).endswith("cv.pdf") or "rb" in mode:
                    file_mock.__enter__.return_value.read.return_value = (
                        b"dummy pdf content"
                    )
                else:
                    # For .env files
                    file_mock.__enter__.return_value.read.return_value = (
                        "HIREFOLIO_GEMINI_API_KEY=test_key"
                    )
                    file_mock.__enter__.return_value.__iter__.return_value = [
                        "HIREFOLIO_GEMINI_API_KEY=test_key"
                    ]
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


@pytest.mark.asyncio
async def test_lifespan_env_local_without_gemini_key(db_session, init_db, monkeypatch):
    """Covers the `.env.local` present but HIREFOLIO_GEMINI_API_KEY unset/empty branch.

    Pre-seed a user and a CV so the lifespan's admin/CV seeding blocks are no-ops and only
    the env-file loading branch is under test.
    """
    monkeypatch.delenv("HIREFOLIO_GEMINI_API_KEY", raising=False)
    db_session.add(
        User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password="hashed",
            is_admin=True,
            is_active=True,
        )
    )
    db_session.add(
        CvDocument(
            filename="cv.pdf",
            data=b"existing",
            version="existing",
            is_active=True,
        )
    )
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi import FastAPI

    from app.main import lifespan

    app = FastAPI()

    @asynccontextmanager
    async def mock_session_cm():
        yield db_session

    with (
        patch("app.main.async_session", side_effect=mock_session_cm),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        patch(
            "os.path.exists", side_effect=lambda path: str(path).endswith(".env.local")
        ),
        patch("dotenv.load_dotenv"),
        patch("builtins.open", new_callable=MagicMock),
    ):
        mock_get.return_value.status_code = 200

        async with lifespan(app):
            pass

    # No new user/CV should have been created; existing rows are untouched.
    result = await db_session.execute(select(User))
    assert len(result.scalars().all()) == 1
    result = await db_session.execute(select(CvDocument))
    assert len(result.scalars().all()) == 1
