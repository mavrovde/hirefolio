from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, Base, async_session
from app.api.posts import router as posts_router
from app.api.auth import router as auth_router
from app.api.stats import router as stats_router
from app.api.tags import router as tags_router
from app.api.ai import router as ai_router


from app.api.cv import router as cv_router
from app.api.admin_cv import router as admin_cv_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = datetime.now(timezone.utc)
    # Create pgvector extension and tables on startup
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

            # Run migrations for existing databases
            # Check if cv_requests table has the new download tracking columns
            result = await conn.execute(
                text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cv_requests' 
                AND column_name IN ('downloaded_at', 'download_count')
            """)
            )
            existing_columns = {row[0] for row in result}

            # Add downloaded_at if it doesn't exist
            if "downloaded_at" not in existing_columns:
                print("Adding downloaded_at column to cv_requests table...")
                await conn.execute(
                    text("""
                    ALTER TABLE cv_requests 
                    ADD COLUMN downloaded_at TIMESTAMP WITH TIME ZONE
                """)
                )
                print("✓ downloaded_at column added")

            # Add download_count if it doesn't exist
            if "download_count" not in existing_columns:
                print("Adding download_count column to cv_requests table...")
                await conn.execute(
                    text("""
                    ALTER TABLE cv_requests 
                    ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0
                """)
                )
                print("✓ download_count column added")

    except Exception as e:
        # Table might not exist yet (first run), which is fine
        print(f"Migration check: {e}")

    # Check and create default admin user if no users exist
    async with async_session() as session:
        from sqlalchemy import select
        from app.models.user import User
        from app.services.auth import get_password_hash

        user_result = await session.execute(select(User))
        user = user_result.scalars().first()

        if not user:
            print("No users found. Creating default admin user 'master'...")
            master_admin = User(
                username="master",
                email="admin@mavrov.de",
                hashed_password=get_password_hash("master"),
                is_admin=True,
                is_active=True,
            )
            session.add(master_admin)
            await session.commit()
            print("Default admin user 'master' created successfully.")

        # Check and seed default CV if no CVs exist
        from app.models.cv_document import CvDocument
        import uuid

        cv_result = await session.execute(select(CvDocument))
        cv_exists = cv_result.scalars().first()

        if not cv_exists:
            static_cv_path = os.path.join(os.path.dirname(__file__), "static", "cv.pdf")
            if os.path.exists(static_cv_path):
                print(f"No CV found in database. Seeding from {static_cv_path}...")
                with open(static_cv_path, "rb") as f:
                    cv_data = f.read()

                default_cv = CvDocument(
                    id=uuid.uuid4(),
                    filename="cv.pdf",
                    data=cv_data,
                    version="1.0.0-fallback",
                    is_active=True,
                )
                session.add(default_cv)
                await session.commit()
                print("Default CV seeded successfully.")
            else:
                print(f"Warning: Fallback CV not found at {static_cv_path}")

    yield


app = FastAPI(
    title="Mavrov.de API",
    description="Backend API for mavrov.de",
    version="1.0.232",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular dev server
        "https://mavrov.de",
        "https://www.mavrov.de",
        "http://mavrov.de",
        "http://www.mavrov.de",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(stats_router)
app.include_router(tags_router)
app.include_router(ai_router)
app.include_router(cv_router)
app.include_router(admin_cv_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Mavrov.de API", "version": app.version}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
