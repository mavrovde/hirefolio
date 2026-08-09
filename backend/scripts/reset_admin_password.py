import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Ensure we can import app
sys.path.append(os.getcwd())

from app.config import settings
from app.services.auth import get_password_hash


async def fixing_admin_hash():
    # SECURITY (issue #142): source the new password from ADMIN_PASSWORD rather
    # than hardcoding a weak default. Refuse to run without it so we never reset
    # the admin to a guessable/empty login.
    new_password = settings.admin_password
    if not new_password:
        print(
            "ERROR: ADMIN_PASSWORD is not set — refusing to reset the admin "
            "password to a weak default. Set ADMIN_PASSWORD and retry."
        )
        return

    print("Generating hash using app.services.auth...")
    hashed_pw = get_password_hash(new_password)
    print(f"Generated Hash: {hashed_pw}")

    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        print("Updating admin password in DB...")
        await session.execute(
            text("UPDATE users SET hashed_password = :h WHERE username = 'admin'"),
            {"h": hashed_pw},
        )
        await session.commit()
        print("Admin password UPDATED.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fixing_admin_hash())
