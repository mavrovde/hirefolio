import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select

from app.database import async_session
from app.models.user import User
from app.services.auth import verify_password


async def verify_admin_password():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()

        if not user:
            print("Admin user not found.")
            return

        password = os.getenv("ADMIN_PASSWORD", "MavrovSecure2026!")
        is_valid = verify_password(password, user.hashed_password)
        if is_valid:
            print("Password verification: SUCCESS")
        else:
            print("Password verification: FAILED")


if __name__ == "__main__":
    asyncio.run(verify_admin_password())
