from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, Base
from app.api.posts import router as posts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Mavrov.de API",
    description="Backend API for mavrov.de",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Mavrov.de API"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
