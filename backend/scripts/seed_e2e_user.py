import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.user import User
from app.services.auth import get_password_hash


async def seed_e2e_user():
    async with async_session() as session:
        print("Seeding E2E admin user...")
        from sqlalchemy import text

        # Obliterate all users and cascading data (like posts) to guarantee a clean E2E environment
        await session.execute(text("TRUNCATE TABLE users CASCADE;"))

        hashed = get_password_hash("admin123")
        print("Creating fresh admin user for E2E...")
        user = User(
            username="admin",
            email="admin@mavrov.de",
            hashed_password=hashed,
            is_admin=True,
            is_active=True,
        )
        session.add(user)

        # Seed Active CV
        print("Seeding active CV document...")
        from app.models.cv_document import CvDocument

        result_cv = await session.execute(
            select(CvDocument).where(CvDocument.is_active.is_(True))
        )
        active_cv = result_cv.scalar_one_or_none()

        if not active_cv:
            print("Creating active CV document...")
            cv = CvDocument(
                filename="e2e_test_cv.pdf",
                data=b"%PDF-1.4 E2E Test Content",
                version="v1.0.0-e2e",
                is_active=True,
            )
            session.add(cv)
        else:
            print("Active CV already exists.")

        await session.commit()
        print("E2E data (user + cv) ready.")


if __name__ == "__main__":
    asyncio.run(seed_e2e_user())
