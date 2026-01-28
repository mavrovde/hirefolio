import asyncio
import os
from sqlalchemy import select
from app.database import async_session
from app.models.cv_document import CvDocument


async def seed_cv():
    async with async_session() as db:
        # Check if active CV exists
        result = await db.execute(select(CvDocument).where(CvDocument.is_active))
        active_cv = result.scalar_one_or_none()

        if active_cv:
            print(f"Active CV already exists: {active_cv.version}")
            return

        # Path to initial CV
        cv_path = "app/static/cv.pdf"
        if not os.path.exists(cv_path):
            print(f"No initial CV file found at {cv_path}. Skipping seed.")
            return

        print(f"Seeding DB with initial CV from {cv_path}...")
        with open(cv_path, "rb") as f:
            content = f.read()

        new_cv = CvDocument(
            filename="cv.pdf", data=content, version="v1.0.initial", is_active=True
        )
        db.add(new_cv)
        await db.commit()
        print("Successfully seeded initial CV (v1.0.initial)")


if __name__ == "__main__":
    asyncio.run(seed_cv())
