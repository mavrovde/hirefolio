import asyncio
import os
import sys

from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


async def add_tags_column():
    async with engine.begin() as conn:
        try:
            print("Checking if 'tags' column exists...")
            # Check if column exists
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='posts' AND column_name='tags'"
                )
            )

            if result.scalar():
                print("'tags' column already exists.")
            else:
                print("Adding 'tags' column...")
                await conn.execute(
                    text("ALTER TABLE posts ADD COLUMN tags VARCHAR[] DEFAULT '{}'")
                )
                print("'tags' column added successfully.")

        except Exception as e:
            print(f"Error migrating database: {e}")


if __name__ == "__main__":
    asyncio.run(add_tags_column())
