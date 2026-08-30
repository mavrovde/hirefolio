"""One-off backfill: encrypt any plaintext ``users.gemini_api_key`` at rest.

Why this exists (issue #143): the ``encrypt0002`` migration runs *once* at
deploy time. If ``GEMINI_ENCRYPTION_KEY`` was still empty when it ran (the prod
default), the migration only widened the column and left existing keys as
plaintext — setting the key afterwards does NOT retroactively encrypt them.

Two ways to encrypt existing rows after enabling the key:
  1. Re-save the key via the admin profile UI (the write path encrypts), or
  2. Run this script once:  ``python -m scripts.backfill_encrypt_gemini_key``
     (with ``GEMINI_ENCRYPTION_KEY`` set in the environment).

It is **idempotent** (skips values already carrying the ``enc:v1:`` marker) and
a **no-op** when the key is unset (it refuses rather than storing plaintext as
"encrypted").
"""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Ensure we can import app (mirrors the other scripts/*.py utilities).
sys.path.append(os.getcwd())

from app.config import settings
from app.services.crypto import _ENC_PREFIX, encrypt


async def backfill() -> int:
    """Encrypt plaintext keys in place. Returns the number of rows updated."""
    if not settings.gemini_encryption_key:
        print(
            "ERROR: HIREFOLIO_GEMINI_ENCRYPTION_KEY is not set — refusing to run. Set it "
            "first, otherwise there is nothing to encrypt with."
        )
        return 0

    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    updated = 0
    try:
        async with async_session() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, gemini_api_key FROM users "
                        "WHERE gemini_api_key IS NOT NULL"
                    )
                )
            ).all()
            for row in rows:
                raw = row.gemini_api_key
                if raw.startswith(_ENC_PREFIX):
                    continue  # already encrypted — idempotent
                enc = encrypt(raw)
                await session.execute(
                    text("UPDATE users SET gemini_api_key = :v WHERE id = :id"),
                    {"v": enc, "id": row.id},
                )
                updated += 1
            await session.commit()
    finally:
        await engine.dispose()

    print(f"Backfill complete: {updated} row(s) encrypted.")
    return updated


if __name__ == "__main__":
    asyncio.run(backfill())
