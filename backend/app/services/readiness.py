"""Startup-readiness checks (issue #124).

The container entrypoint runs ``alembic upgrade head`` *before* exec-ing
uvicorn, but a fresh stack has no true readiness signal for the backend, so an
orchestrator / the E2E gate can start hammering endpoints during the migration
window. A read hitting a not-yet-created table (e.g. ``profile_snapshots``)
otherwise surfaces as a raw ``500`` (``asyncpg.UndefinedTableError``).

``schema_ready`` lets ``/health`` reflect *true* readiness (required tables
present), and ``is_undefined_table_error`` lets read endpoints downgrade the
warm-up window to a graceful, retryable ``503`` instead of a raw ``500``.
"""

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

# SQLSTATE 42P01 = ``undefined_table`` — raised (as asyncpg's UndefinedTableError,
# wrapped by SQLAlchemy's ProgrammingError) when a query hits a table the
# migrations have not created yet.
UNDEFINED_TABLE_SQLSTATE = "42P01"

# Tables that MUST exist before the app can serve public read traffic. Kept
# minimal on purpose: the public read paths that triggered #124.
REQUIRED_TABLES: tuple[str, ...] = ("profile_snapshots",)


def is_undefined_table_error(exc: ProgrammingError) -> bool:
    """Return True when ``exc`` was caused by querying a not-yet-created table."""
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    return sqlstate == UNDEFINED_TABLE_SQLSTATE


async def schema_ready(session: AsyncSession) -> bool:
    """Return True only when every required table exists in the database.

    Uses ``to_regclass`` (returns NULL for an absent relation) so the probe is a
    single cheap catalog lookup per table and never raises on a missing table.
    """
    for table in REQUIRED_TABLES:
        exists = await session.scalar(
            text("SELECT to_regclass(:qualified_name) IS NOT NULL"),
            {"qualified_name": f"public.{table}"},
        )
        if not exists:
            return False
    return True
