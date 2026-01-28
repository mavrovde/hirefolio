from contextlib import asynccontextmanager

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
    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Check and create default admin user if no users exist
    async with async_session() as session:
        from sqlalchemy import select
        from app.models.user import User
        from app.services.auth import get_password_hash

        result = await session.execute(select(User))
        user = result.scalars().first()

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

    yield


app = FastAPI(
    title="Mavrov.de API",
    description="Backend API for mavrov.de",
    version="1.0.124",
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
