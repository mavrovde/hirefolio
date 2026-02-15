import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base
from app.config import settings
from app.models.user import User
from app.services.auth import create_access_token

# Use a separate test database or the main one if appropriate for this quick test
# ideally use sqlite in memory but we have pg constraints
# Re-using the main env db for this quick verification inside container
SQLALCHEMY_DATABASE_URL = settings.database_url

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()

@pytest_asyncio.fixture
async def async_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def admin_token_headers(db_session):
    # Ensure admin user exists
    from sqlalchemy import select
    from app.services.auth import get_password_hash
    
    result = await db_session.execute(select(User).where(User.username == "admin"))
    user = result.scalars().first()
    if not user:
        user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin"),
            is_admin=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
    
    access_token = create_access_token(data={"sub": "admin", "scopes": ["admin"]})
    return {"Authorization": f"Bearer {access_token}"}
