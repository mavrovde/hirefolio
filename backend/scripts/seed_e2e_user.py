import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.services.auth import get_password_hash


async def seed_e2e_user():
    async with async_session() as session:
        print("Seeding E2E admin user...")
        result = await session.execute(
            select(User).where(User.email == "admin@mavrov.de")
        )
        user = result.scalar_one_or_none()

        hashed = get_password_hash("admin")

        if user:
            print("Updating existing admin user...")
            user.username = "admin"
            user.hashed_password = hashed
            user.is_active = True
            user.is_admin = True
        else:
            print("Creating new admin user...")
            user = User(
                username="admin",
                email="admin@mavrov.de",
                hashed_password=hashed,
                is_admin=True,
                is_active=True,
            )
            session.add(user)

        await session.commit()
        print("E2E user 'admin' ready.")


if __name__ == "__main__":
    asyncio.run(seed_e2e_user())
