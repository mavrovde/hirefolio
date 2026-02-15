import asyncio
from app.database import async_session
from app.models.user import User
from app.services.auth import verify_password
from sqlalchemy import select

async def verify():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if user:
            print(f"User: {user.username}")
            print(f"Hash: {user.hashed_password}")
            is_valid = verify_password("admin123", user.hashed_password)
            print(f"Verify admin123: {is_valid}")
        else:
            print("User admin not found")

if __name__ == "__main__":
    asyncio.run(verify())
