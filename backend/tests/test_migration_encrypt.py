"""Regression tests for the ``encrypt0002`` migration (issue #143).

Coverage's ``source=["app"]`` excludes ``backend/migrations/``, so the
encrypt-in-place upgrade, the ``enc:v1:`` idempotent-skip, and — most
importantly — the downgrade's refuse-to-wipe guard would otherwise be entirely
unexercised. These tests run the *real* Alembic migration up/down against a
throwaway ``test_*`` Postgres database and assert both the key-SET and key-UNSET
behaviours, including that a rollback can never overwrite an encrypted
credential with NULL.

They are **synchronous** on purpose: Alembic's ``env.py`` calls ``asyncio.run``
internally, which cannot be nested inside a running event loop — so DB
setup/teardown here also uses ``asyncio.run`` rather than pytest-asyncio.

NOTE (CLAUDE.md rule 10): the Fernet keys are generated locally per-test — they
are encryption keys, not paid-service credentials.
"""

import asyncio
import os

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy.engine.url import make_url

from app.config import settings

# Worker-scoped: under `pytest -n auto` several xdist workers run these tests
# concurrently, and a SHARED scratch database means one worker drops the database
# another is mid-migration on (observed on main: 3 failed + 1 error). The
# `test_` prefix is preserved so the CLAUDE.md rule-9 carve-out still applies.
SCRATCH_DB = f"test_mavrov_encmig_{os.getenv('PYTEST_XDIST_WORKER', 'main')}"

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")


def _params() -> tuple[str, int, str, str]:
    """Host/port/user/password from the configured (pre-patch) test DB URL."""
    url = make_url(settings.database_url)
    return (
        url.host or "127.0.0.1",
        url.port or 5433,
        url.username or "postgres",
        (url.password or "postgres"),
    )


def _admin_dsn() -> str:
    host, port, user, pw = _params()
    return f"postgresql://{user}:{pw}@{host}:{port}/postgres"


def _scratch_async_url() -> str:
    host, port, user, pw = _params()
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{SCRATCH_DB}"


def _scratch_dsn() -> str:
    host, port, user, pw = _params()
    return f"postgresql://{user}:{pw}@{host}:{port}/{SCRATCH_DB}"


async def _create_scratch() -> None:
    conn = await asyncpg.connect(_admin_dsn())
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            SCRATCH_DB,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        await conn.execute(f'CREATE DATABASE "{SCRATCH_DB}"')
    finally:
        await conn.close()


async def _drop_scratch() -> None:
    conn = await asyncpg.connect(_admin_dsn())
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            SCRATCH_DB,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
    finally:
        await conn.close()


async def _seed(id_: int, username: str, key_value: str | None) -> None:
    conn = await asyncpg.connect(_scratch_dsn())
    try:
        await conn.execute(
            "INSERT INTO users (id, username, email, hashed_password, is_admin, "
            "is_active, gemini_api_key, created_at) "
            "VALUES ($1, $2, $3, 'h', true, true, $4, now())",
            id_,
            username,
            f"{username}@example.com",
            key_value,
        )
    finally:
        await conn.close()


async def _fetch_key(id_: int) -> str | None:
    conn = await asyncpg.connect(_scratch_dsn())
    try:
        return await conn.fetchval(
            "SELECT gemini_api_key FROM users WHERE id = $1", id_
        )
    finally:
        await conn.close()


async def _column_varchar_len() -> int | None:
    """None when the column is TEXT, an int when it is VARCHAR(n)."""
    conn = await asyncpg.connect(_scratch_dsn())
    try:
        return await conn.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'gemini_api_key'"
        )
    finally:
        await conn.close()


def _alembic_config() -> Config:
    # File-less Config so env.py skips fileConfig() (no global logging side
    # effects on the rest of the suite). env.py overrides sqlalchemy.url from
    # settings.database_url, which each test monkeypatches to the scratch DB.
    cfg = Config()
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    return cfg


@pytest.fixture
def scratch_db():
    asyncio.run(_create_scratch())
    try:
        yield
    finally:
        asyncio.run(_drop_scratch())


def test_upgrade_encrypts_in_place_and_is_idempotent_key_set(monkeypatch, scratch_db):
    """key SET: plaintext encrypted in place; pre-encrypted row untouched; down decrypts back."""
    key = Fernet.generate_key().decode()
    fernet = Fernet(key.encode())
    monkeypatch.setattr(settings, "database_url", _scratch_async_url())
    monkeypatch.setattr(settings, "gemini_encryption_key", key)
    cfg = _alembic_config()

    command.upgrade(cfg, "baseline0001")
    # Row A: legacy plaintext. Row B: already encrypted (idempotency probe).
    already = "enc:v1:" + fernet.encrypt(b"already-secret").decode()
    asyncio.run(_seed(1, "plainuser", "plain-secret"))
    asyncio.run(_seed(2, "encuser", already))

    command.upgrade(cfg, "encrypt0002")

    a = asyncio.run(_fetch_key(1))
    assert a is not None and a.startswith("enc:v1:")
    assert "plain-secret" not in a  # ciphertext, not plaintext at rest
    assert fernet.decrypt(a[len("enc:v1:") :].encode()).decode() == "plain-secret"
    # Idempotent skip: the already-encrypted row is byte-for-byte unchanged
    # (NOT double-wrapped).
    b = asyncio.run(_fetch_key(2))
    assert b == already
    assert fernet.decrypt(b[len("enc:v1:") :].encode()).decode() == "already-secret"

    command.downgrade(cfg, "baseline0001")
    assert asyncio.run(_fetch_key(1)) == "plain-secret"
    assert asyncio.run(_fetch_key(2)) == "already-secret"
    assert asyncio.run(_column_varchar_len()) == 255


def test_upgrade_is_noop_widen_when_key_unset(monkeypatch, scratch_db):
    """key UNSET: upgrade only widens (no encryption); downgrade does not wipe."""
    monkeypatch.setattr(settings, "database_url", _scratch_async_url())
    monkeypatch.setattr(settings, "gemini_encryption_key", "")
    cfg = _alembic_config()

    command.upgrade(cfg, "baseline0001")
    asyncio.run(_seed(1, "plainuser", "plain-secret"))

    command.upgrade(cfg, "encrypt0002")
    # No key -> value left as plaintext, column widened to TEXT (len == None).
    assert asyncio.run(_fetch_key(1)) == "plain-secret"
    assert asyncio.run(_column_varchar_len()) is None

    command.downgrade(cfg, "baseline0001")
    # Non-prefixed row is skipped, NOT wiped; column narrowed back.
    assert asyncio.run(_fetch_key(1)) == "plain-secret"
    assert asyncio.run(_column_varchar_len()) == 255


def test_downgrade_refuses_to_wipe_encrypted_row_without_key(monkeypatch, scratch_db):
    """REGRESSION: downgrade must abort (not NULL-wipe) when the key is gone.

    The previous implementation wrote ``decrypt(raw)`` back unconditionally; with
    the key unset ``decrypt`` returns None, so the encrypted credential became
    NULL — an unrecoverable wipe on rollback. This asserts the row survives.
    """
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "database_url", _scratch_async_url())
    monkeypatch.setattr(settings, "gemini_encryption_key", key)
    cfg = _alembic_config()

    command.upgrade(cfg, "baseline0001")
    asyncio.run(_seed(1, "plainuser", "plain-secret"))
    command.upgrade(cfg, "encrypt0002")
    encrypted = asyncio.run(_fetch_key(1))
    assert encrypted is not None and encrypted.startswith("enc:v1:")

    # Simulate the key being missing/rotated at downgrade time.
    monkeypatch.setattr(settings, "gemini_encryption_key", "")
    with pytest.raises(Exception) as exc:
        command.downgrade(cfg, "baseline0001")
    assert "refusing to overwrite" in str(exc.value).lower()

    # The encrypted credential is still intact — NOT wiped to NULL.
    assert asyncio.run(_fetch_key(1)) == encrypted


def test_backfill_encrypts_plaintext_and_is_idempotent(monkeypatch, scratch_db):
    """The post-deploy backfill encrypts leftover plaintext; re-run is a no-op."""
    from scripts.backfill_encrypt_gemini_key import backfill

    key = Fernet.generate_key().decode()
    fernet = Fernet(key.encode())
    monkeypatch.setattr(settings, "database_url", _scratch_async_url())
    monkeypatch.setattr(settings, "gemini_encryption_key", key)
    cfg = _alembic_config()

    command.upgrade(cfg, "encrypt0002")
    asyncio.run(_seed(1, "plainuser", "plain-secret"))

    assert asyncio.run(backfill()) == 1
    v = asyncio.run(_fetch_key(1))
    assert v is not None and v.startswith("enc:v1:")
    assert fernet.decrypt(v[len("enc:v1:") :].encode()).decode() == "plain-secret"

    # Idempotent: already-encrypted row is skipped on a second run.
    assert asyncio.run(backfill()) == 0


def test_backfill_refuses_without_key(monkeypatch):
    """The backfill refuses (returns 0) when HIREFOLIO_GEMINI_ENCRYPTION_KEY is unset."""
    from scripts.backfill_encrypt_gemini_key import backfill

    monkeypatch.setattr(settings, "gemini_encryption_key", "")
    assert asyncio.run(backfill()) == 0
