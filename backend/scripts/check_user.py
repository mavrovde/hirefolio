import asyncio
import sys
import os

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.services.auth import verify_password

async def check():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            print("User admin NOT FOUND")
        else:
            print(f"User found. Hash starts with {user.hashed_password[:10]}. Active: {user.is_active}")
            print(f"Verify 'admin': {verify_password('admin', user.hashed_password)}")
            print(f"Verify 'admin123': {verify_password('admin123', user.hashed_password)}")

if __name__ == "__main__":
    asyncio.run(check())
