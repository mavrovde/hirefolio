import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import update

from app.database import async_session
from app.models.user import User
from app.services.auth import get_password_hash


async def reset_password():
    async with async_session() as session:
        print("Resetting admin password...")
        hashed_password = get_password_hash("admin")

        # Update proper
        await session.execute(
            update(User)
            .where(User.username == "admin")
            .values(hashed_password=hashed_password, is_active=True)
        )
        await session.commit()
        print("Password reset successfully.")


if __name__ == "__main__":
    asyncio.run(reset_password())
