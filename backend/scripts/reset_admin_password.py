import sys
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Ensure we can import app
sys.path.append(os.getcwd())

from app.config import settings
from app.services.auth import get_password_hash


async def fixing_admin_hash():
    print("Generating hash using app.services.auth...")
    hashed_pw = get_password_hash("admin123")
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
