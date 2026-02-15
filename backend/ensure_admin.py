import asyncio
from app.database import get_async_session
from app.services.auth import get_password_hash
from app.models.user import User
from sqlalchemy import select
from app.config import settings

async def check_create_admin():
    async for session in get_async_session():
        print("Checking for admin user...")
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Admin user found: {user.username}")
            # Reset password to ensure it's admin123
            user.hashed_password = get_password_hash("admin123")
            session.add(user)
            await session.commit()
            print("Admin password reset to 'admin123'")
        else:
            print("Admin user NOT found. Creating...")
            new_admin = User(
                username="admin",
                email="admin@mavrov.de",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_admin=True,
                gemini_api_key=settings.gemini_api_key or "test-key"
            )
            session.add(new_admin)
            await session.commit()
            print("Admin user created.")
        break

if __name__ == "__main__":
    asyncio.run(check_create_admin())
