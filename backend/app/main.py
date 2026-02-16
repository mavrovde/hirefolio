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
from app.api.admin_sql import router as admin_sql_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.now(timezone.utc)}] LIFESPAN START: Mavrov.de API")
    app.state.start_time = datetime.now(timezone.utc)

    # Check Ollama connection
    from app.config import settings
    import httpx

    print(
        f"[{datetime.now(timezone.utc)}] INFRA CHECK: Checking Ollama at {settings.ollama_url}..."
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=10)
            print(
                f"[{datetime.now(timezone.utc)}] INFRA CHECK: Ollama status: {resp.status_code}"
            )
    except Exception as e:
        print(
            f"[{datetime.now(timezone.utc)}] INFRA CHECK WARNING: Ollama connectivity check failed: {e}"
        )

    # Create pgvector extension and tables on startup
    print(
        f"[{datetime.now(timezone.utc)}] DB START: Running migrations and extension checks..."
    )
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
                print(
                    f"[{datetime.now(timezone.utc)}] DB MIGRATION: Adding downloaded_at column to cv_requests table..."
                )
                await conn.execute(
                    text("""
                    ALTER TABLE cv_requests 
                    ADD COLUMN downloaded_at TIMESTAMP WITH TIME ZONE
                """)
                )
                print(
                    f"[{datetime.now(timezone.utc)}] DB MIGRATION: ✓ downloaded_at column added"
                )

            # Add download_count if it doesn't exist
            if "download_count" not in existing_columns:
                print(
                    f"[{datetime.now(timezone.utc)}] DB MIGRATION: Adding download_count column to cv_requests table..."
                )
                await conn.execute(
                    text("""
                    ALTER TABLE cv_requests 
                    ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0
                """)
                )
                print(
                    f"[{datetime.now(timezone.utc)}] DB MIGRATION: ✓ download_count column added"
                )

    except Exception as e:
        # Table might not exist yet (first run), which is fine
        print(
            f"[{datetime.now(timezone.utc)}] DB MIGRATION ERROR: Migration check: {e}"
        )


    # Check and seed default admin user if no users exist
    print(f"[{datetime.now(timezone.utc)}] DB SEED: Checking default admin user...")
    
    # Load local env for development seeding (ignored in git)
    local_env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    gemini_key_seed = None
    if os.path.exists(local_env_path):
        print(f"[{datetime.now(timezone.utc)}] DB SEED: Found local env file at {local_env_path}")
        from dotenv import load_dotenv
        load_dotenv(local_env_path)
        gemini_key_seed = os.getenv("GEMINI_API_KEY")
        if gemini_key_seed:
            print(f"[{datetime.now(timezone.utc)}] DB SEED: Loaded GEMINI_API_KEY from local env for seeding.")

    async with async_session() as session:
        from sqlalchemy import select
        from app.models.user import User
        from app.services.auth import get_password_hash

        user_result = await session.execute(select(User))
        user = user_result.scalars().first()

        if not user:
            print(
                f"[{datetime.now(timezone.utc)}] DB SEED: No users found. Creating default admin user 'admin'..."
            )
            default_admin = User(
                username="admin",
                email="admin@mavrov.de",
                hashed_password=get_password_hash("admin"),
                is_admin=True,
                is_active=True,
                gemini_api_key=gemini_key_seed,
            )
            session.add(default_admin)
            await session.commit()
            print(
                f"[{datetime.now(timezone.utc)}] DB SEED: Default admin user 'admin' created successfully."
            )
        elif gemini_key_seed and not user.gemini_api_key:
             # Optional: Update existing admin if key is missing and we have one locally
             print(f"[{datetime.now(timezone.utc)}] DB SEED: Admin exists but has no key. Injecting from local env...")
             user.gemini_api_key = gemini_key_seed
             session.add(user)
             await session.commit()

    # Check and seed default CV if no CVs exist
    from app.models.cv_document import CvDocument
    import uuid

    cv_result = await session.execute(select(CvDocument))
    cv_exists = cv_result.scalars().first()

    if not cv_exists:
        static_cv_path = os.path.join(os.path.dirname(__file__), "static", "cv.pdf")
        if os.path.exists(static_cv_path):
            print(
                f"[{datetime.now(timezone.utc)}] DB SEED: No CV found in database. Seeding from {static_cv_path}..."
            )
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
            print(
                f"[{datetime.now(timezone.utc)}] DB SEED: Default CV seeded successfully."
            )
        else:
            print(
                f"[{datetime.now(timezone.utc)}] DB SEED WARNING: Fallback CV not found at {static_cv_path}"
            )

    print(f"[{datetime.now(timezone.utc)}] LIFESPAN READY: Backend is operational.")
    yield
    print(
        f"[{datetime.now(timezone.utc)}] LIFESPAN SHUTDOWN: Mavrov.de API shutting down."
    )


app = FastAPI(
    title="Mavrov.de API",
    description="Backend API for mavrov.de",
    version="1.1.34",
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

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(posts_router, prefix=settings.api_prefix)
app.include_router(stats_router, prefix=settings.api_prefix)
app.include_router(tags_router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)
app.include_router(cv_router, prefix=settings.api_prefix)
app.include_router(admin_cv_router, prefix=settings.api_prefix)
app.include_router(admin_sql_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"message": "Welcome to Mavrov.de API", "version": app.version}


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    return {"status": "healthy"}
