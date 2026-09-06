"""The conftest non-test_* DB guard must itself be pinned (#261 review, rule 2).

The guard (`conftest._test_database_url`) is lesson §4 enforced in code: the
suite drop/creates tables, so pointing it at a non-`test_*` database silently
destroys dev data (it happened). A guard with no test is the "gate that
doesn't gate" class (§16/§18) — these cases fail with the guard reverted.
"""

import pytest
from _pytest.outcomes import Exit

from conftest import _test_database_url


def test_refuses_non_test_database(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+asyncpg://p:p@127.0.0.1:5433/mavrov"
    )
    with pytest.raises(Exit) as exc:
        _test_database_url()
    assert "REFUSING" in str(exc.value)


def test_refuses_the_app_default_fallthrough(monkeypatch):
    """The historical incident shape: TEST_DATABASE_URL unset, resolution falls
    through to a dev-looking DATABASE_URL — must refuse, not clobber."""
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://p:p@127.0.0.1:5433/mavrov")
    with pytest.raises(Exit):
        _test_database_url()


def test_accepts_test_database(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+asyncpg://p:p@127.0.0.1:5433/test_anything"
    )
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    assert _test_database_url().database == "test_anything"


def test_xdist_suffix_keeps_the_test_prefix(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+asyncpg://p:p@127.0.0.1:5433/test_anything"
    )
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    db = _test_database_url().database
    assert db == "test_anything_gw3"
    assert db.startswith("test_")
