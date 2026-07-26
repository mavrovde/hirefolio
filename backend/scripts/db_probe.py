"""Detect the database's migration state so the entrypoint can self-adopt.

Used by ``docker-entrypoint.sh`` to decide how to safely bring any of the
three possible database states up to date with Alembic, with **no manual
step required** (see issue #46):

- ``FRESH``: no ``alembic_version`` table and no known core table (e.g.
  ``users``) exist yet. Just run ``alembic upgrade head`` — it creates the
  full schema from scratch.
- ``PRE_ALEMBIC``: core tables already exist (built by the old
  ``Base.metadata.create_all``) but ``alembic_version`` does not. This is
  the current prod case. Running ``alembic upgrade head`` directly would
  try to ``CREATE TABLE`` objects that already exist and crash. The
  database must first be stamped at the baseline revision (records the
  revision *without* running any DDL), then upgraded to head.
- ``ALEMBIC_MANAGED``: ``alembic_version`` already exists — the normal,
  steady-state path. Just run ``alembic upgrade head`` (a no-op once
  already at head).

Prints exactly one of the three keywords above to stdout and exits 0.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg

from app.config import settings

FRESH = "FRESH"
PRE_ALEMBIC = "PRE_ALEMBIC"
ALEMBIC_MANAGED = "ALEMBIC_MANAGED"


def _asyncpg_dsn(database_url: str) -> str:
    """asyncpg.connect() wants a plain postgresql:// DSN, not a SQLAlchemy URL."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


async def probe(database_url: str | None = None) -> str:
    conn = await asyncpg.connect(_asyncpg_dsn(database_url or settings.database_url))
    try:
        has_alembic_version = await conn.fetchval(
            "SELECT to_regclass('public.alembic_version') IS NOT NULL"
        )
        if has_alembic_version:
            return ALEMBIC_MANAGED

        has_core_table = await conn.fetchval(
            "SELECT to_regclass('public.users') IS NOT NULL"
        )
        return PRE_ALEMBIC if has_core_table else FRESH
    finally:
        await conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.stdout.write(asyncio.run(probe()))
