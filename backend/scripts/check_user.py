import asyncio
import sys
import os

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.user import User


async def check():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            print("User admin NOT FOUND")
        else:
            print("User found. Checking status...")
            print(f"User Active: {user.is_active}")


if __name__ == "__main__":
    asyncio.run(check())
