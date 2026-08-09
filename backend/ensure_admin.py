import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import get_async_session
from app.models.user import User
from app.services.auth import get_password_hash


async def check_create_admin():
    # SECURITY (issue #142): require ADMIN_PASSWORD; never fall back to a weak
    # hardcoded default. Refuse to run rather than set an empty/guessable login.
    if not settings.admin_password:
        print(
            "ERROR: ADMIN_PASSWORD is not set — refusing to create/reset the "
            "admin with a weak-default password. Set ADMIN_PASSWORD and retry."
        )
        return

    async for session in get_async_session():
        print("Checking for admin user...")
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()

        if user:
            print(f"Admin user found: {user.username}")
            # Reset password to the configured ADMIN_PASSWORD
            user.hashed_password = get_password_hash(settings.admin_password)
            session.add(user)
            await session.commit()
            print("Admin password reset to configured ADMIN_PASSWORD")
        else:
            print("Admin user NOT found. Creating...")
            new_admin = User(
                username="admin",
                email=settings.default_admin_email,
                hashed_password=get_password_hash(settings.admin_password),
                is_active=True,
                is_admin=True,
                gemini_api_key=settings.gemini_api_key or None,
            )
            session.add(new_admin)
            await session.commit()
            print("Admin user created.")
        break


if __name__ == "__main__":
    asyncio.run(check_create_admin())
