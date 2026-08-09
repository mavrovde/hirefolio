"""Unit tests for the startup-readiness helpers (issue #124)."""

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.services.readiness import (
    UNDEFINED_TABLE_SQLSTATE,
    is_undefined_table_error,
    schema_ready,
)


class _FakeOrig(Exception):
    """Stand-in for an asyncpg error carrying a SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def _programming_error(sqlstate: str | None) -> ProgrammingError:
    orig = _FakeOrig(sqlstate) if sqlstate is not None else None
    return ProgrammingError("SELECT 1", {}, orig)


def test_is_undefined_table_error_true_for_undefined_table():
    exc = _programming_error(UNDEFINED_TABLE_SQLSTATE)
    assert is_undefined_table_error(exc) is True


def test_is_undefined_table_error_false_for_other_sqlstate():
    # 42703 = undefined_column: a real DB error that is NOT a warm-up race.
    exc = _programming_error("42703")
    assert is_undefined_table_error(exc) is False


def test_is_undefined_table_error_false_when_no_orig():
    exc = _programming_error(None)
    assert is_undefined_table_error(exc) is False


async def test_schema_ready_true_when_tables_present(db_session):
    assert await schema_ready(db_session) is True


async def test_schema_ready_false_when_required_table_missing(db_session):
    await db_session.execute(text("DROP TABLE profile_snapshots"))
    await db_session.commit()
    assert await schema_ready(db_session) is False
