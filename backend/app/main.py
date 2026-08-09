import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_cv import router as admin_cv_router
from app.api.admin_profile import router as admin_profile_router
from app.api.admin_sql import router as admin_sql_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.cv import router as cv_router
from app.api.linkedin import router as linkedin_router
from app.api.posts import router as posts_router
from app.api.profile import router as profile_router
from app.api.stats import router as stats_router
from app.api.tags import router as tags_router
from app.api.years import router as years_router
from app.config import settings
from app.database import async_session, get_db
from app.services.readiness import schema_ready


def _read_file_bytes(path: str) -> bytes:
    """Blocking file read, meant to be run off the event loop via asyncio.to_thread."""
    with open(path, "rb") as f:
        return f.read()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.now(UTC)}] LIFESPAN START: Mavrov.de API")
    app.state.start_time = datetime.now(UTC)

    # Check Ollama connection
    import httpx

    from app.config import settings

    print(
        f"[{datetime.now(UTC)}] INFRA CHECK: Checking Ollama at {settings.ollama_url}..."
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=10)
            print(
                f"[{datetime.now(UTC)}] INFRA CHECK: Ollama status: {resp.status_code}"
            )
    except Exception as e:
        print(
            f"[{datetime.now(UTC)}] INFRA CHECK WARNING: Ollama connectivity check failed: {e}"
        )

    # Schema management is now exclusively Alembic's job: the container
    # entrypoint (see Dockerfile / docker-entrypoint.sh) runs `alembic upgrade
    # head` before this process starts, so by the time lifespan runs, the
    # schema (including the `vector` extension) is already up to date. See
    # "Database Migrations" in the root README.md for the full workflow.

    # Check and seed default admin user if no users exist
    print(f"[{datetime.now(UTC)}] DB SEED: Checking default admin user...")

    # Load local env for development seeding (ignored in git)
    local_env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    gemini_key_seed = None
    if os.path.exists(local_env_path):
        print(
            f"[{datetime.now(UTC)}] DB SEED: Found local env file at {local_env_path}"
        )
        from dotenv import load_dotenv

        load_dotenv(local_env_path)
        gemini_key_seed = os.getenv("GEMINI_API_KEY")
        if gemini_key_seed:
            print(
                f"[{datetime.now(UTC)}] DB SEED: Loaded GEMINI_API_KEY from local env for seeding."
            )

    async with async_session() as session:
        from sqlalchemy import select

        from app.models.user import User
        from app.services.auth import get_password_hash

        user_result = await session.execute(select(User))
        user = user_result.scalars().first()

        if not user:
            print(
                f"[{datetime.now(UTC)}] DB SEED: No users found. Creating default admin user 'admin'..."
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
                f"[{datetime.now(UTC)}] DB SEED: Default admin user 'admin' created successfully."
            )
        elif gemini_key_seed and not user.gemini_api_key:
            # Optional: Update existing admin if key is missing and we have one locally
            print(
                f"[{datetime.now(UTC)}] DB SEED: Admin exists but has no key. Injecting from local env..."
            )
            user.gemini_api_key = gemini_key_seed
            session.add(user)
            await session.commit()

    # Check and seed default CV if no CVs exist
    import uuid

    from app.models.cv_document import CvDocument

    cv_result = await session.execute(select(CvDocument))
    cv_exists = cv_result.scalars().first()

    if not cv_exists:
        static_cv_path = os.path.join(os.path.dirname(__file__), "static", "cv.pdf")
        if os.path.exists(static_cv_path):
            print(
                f"[{datetime.now(UTC)}] DB SEED: No CV found in database. Seeding from {static_cv_path}..."
            )
            cv_data = await asyncio.to_thread(_read_file_bytes, static_cv_path)

            default_cv = CvDocument(
                id=uuid.uuid4(),
                filename="cv.pdf",
                data=cv_data,
                version="1.0.0-fallback",
                is_active=True,
            )
            session.add(default_cv)
            await session.commit()
            print(f"[{datetime.now(UTC)}] DB SEED: Default CV seeded successfully.")
        else:
            print(
                f"[{datetime.now(UTC)}] DB SEED WARNING: Fallback CV not found at {static_cv_path}"
            )

    print(f"[{datetime.now(UTC)}] LIFESPAN READY: Backend is operational.")
    yield
    print(f"[{datetime.now(UTC)}] LIFESPAN SHUTDOWN: Mavrov.de API shutting down.")


app = FastAPI(
    title="Mavrov.de API",
    description="Backend API for mavrov.de",
    version="1.8.2",
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
app.include_router(linkedin_router, prefix=settings.api_prefix)
app.include_router(years_router, prefix=settings.api_prefix)
app.include_router(profile_router, prefix=settings.api_prefix)
app.include_router(admin_profile_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"message": "Welcome to Mavrov.de API", "version": app.version}


@app.get(f"{settings.api_prefix}/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Readiness probe: 200 only once the schema (migrations) is present.

    Returns a retryable ``503`` during the startup window where uvicorn is up
    but ``alembic upgrade head`` (run by ``docker-entrypoint.sh``) has not yet
    created the tables (issue #124), so orchestrators / the E2E gate can wait on
    *true* readiness instead of racing into a raw ``500`` UndefinedTableError.
    """
    try:
        ready = await schema_ready(db)
    except SQLAlchemyError:
        # DB unreachable / connection still coming up — not ready, retry later.
        ready = False
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "initializing", "ready": False},
        )
    return JSONResponse(content={"status": "healthy", "ready": True})


@app.get(f"{settings.api_prefix}/ping")
async def ping() -> dict[str, str]:
    return {"ping": "ok"}
