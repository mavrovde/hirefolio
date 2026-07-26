from sqlalchemy import text

from app.database import engine


async def upgrade():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE cv_requests ADD COLUMN subscribe_to_updates BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )


async def downgrade():
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE cv_requests DROP COLUMN subscribe_to_updates")
        )
