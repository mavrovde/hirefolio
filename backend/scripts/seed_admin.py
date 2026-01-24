import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from app.database import async_session
from app.models.user import User
from app.services.auth import get_password_hash


async def seed_admin():
    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()

        if user:
            print("Admin user already exists.")
            return

        print("Creating admin user...")
        hashed_password = get_password_hash("admin")
        new_admin = User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password=hashed_password,
            is_admin=True,
            is_active=True,
        )
        session.add(new_admin)
        await session.commit()
        print("Admin user created successfully.")


if __name__ == "__main__":
    asyncio.run(seed_admin())
