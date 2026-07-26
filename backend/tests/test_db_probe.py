"""Unit tests for scripts/db_probe.py — the entrypoint's DB self-adoption probe.

Not part of the `app` package (so not counted in the --cov=app gate), but this
is exactly the logic issue #46's automatic self-adoption depends on, so it
gets its own regression coverage: all three DB states, plus the DSN
conversion helper.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.db_probe import ALEMBIC_MANAGED, FRESH, PRE_ALEMBIC, _asyncpg_dsn, probe


def _mock_conn(fetchval_side_effect):
    conn = AsyncMock()
    conn.fetchval.side_effect = fetchval_side_effect
    return conn


@pytest.mark.asyncio
async def test_probe_fresh_database():
    """Neither alembic_version nor a core table exists: FRESH."""
    conn = _mock_conn([False, False])
    with patch("scripts.db_probe.asyncpg.connect", AsyncMock(return_value=conn)):
        result = await probe("postgresql://u:p@h/db")

    assert result == FRESH
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_pre_alembic_database():
    """Core table (users) exists but alembic_version does not: PRE_ALEMBIC."""
    conn = _mock_conn([False, True])
    with patch("scripts.db_probe.asyncpg.connect", AsyncMock(return_value=conn)):
        result = await probe("postgresql://u:p@h/db")

    assert result == PRE_ALEMBIC
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_alembic_managed_database():
    """alembic_version already exists: ALEMBIC_MANAGED (only one query needed)."""
    conn = _mock_conn([True])
    with patch("scripts.db_probe.asyncpg.connect", AsyncMock(return_value=conn)):
        result = await probe("postgresql://u:p@h/db")

    assert result == ALEMBIC_MANAGED
    assert conn.fetchval.await_count == 1
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_closes_connection_even_on_error():
    """The connection is always closed, even if a query raises."""
    conn = AsyncMock()
    conn.fetchval.side_effect = RuntimeError("boom")
    with (
        patch("scripts.db_probe.asyncpg.connect", AsyncMock(return_value=conn)),
        pytest.raises(RuntimeError),
    ):
        await probe("postgresql://u:p@h/db")

    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_defaults_to_settings_database_url():
    """No explicit URL: falls back to settings.database_url."""
    conn = _mock_conn([True])
    with (
        patch(
            "scripts.db_probe.asyncpg.connect", AsyncMock(return_value=conn)
        ) as mock_connect,
        patch("scripts.db_probe.settings") as mock_settings,
    ):
        mock_settings.database_url = "postgresql+asyncpg://u:p@h/db"
        result = await probe()

    assert result == ALEMBIC_MANAGED
    mock_connect.assert_awaited_once_with("postgresql://u:p@h/db")


def test_asyncpg_dsn_converts_sqlalchemy_asyncpg_url():
    assert _asyncpg_dsn("postgresql+asyncpg://u:p@h/db") == "postgresql://u:p@h/db"


def test_asyncpg_dsn_leaves_plain_url_unchanged():
    assert _asyncpg_dsn("postgresql://u:p@h/db") == "postgresql://u:p@h/db"
