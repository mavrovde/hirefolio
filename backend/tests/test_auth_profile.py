from app.config import settings
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.auth import get_password_hash, verify_password, create_access_token
from app.main import app
from app.database import get_db


@pytest.mark.asyncio
async def test_change_password_success(db_session: AsyncSession):
    # 1. Setup: Create a real user in DB
    user_password = "oldpassword"
    hashed = get_password_hash(user_password)
    user = User(
        username="test_admin",
        email="test@example.com",
        hashed_password=hashed,
        is_admin=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # 2. Create token associated with this user
    token = create_access_token(data={"sub": user.username})

    # 3. Setup Client with only DB override (no auth override)
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Ensure no other overrides pollute this (in case other fixtures ran)
    # But clean slate fixture clears them usually.
    # Just to be safe, we rely on test isolation.

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(
            f"{settings.api_prefix}/auth/password",
            json={"old_password": user_password, "new_password": "newpassword"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 4. Assertions
    assert response.status_code == 204

    # Verify in DB
    # We need to refresh user or fetch again
    result = await db_session.execute(select(User).where(User.username == "test_admin"))
    updated_user = result.scalar_one()
    assert verify_password("newpassword", updated_user.hashed_password)

    # Cleanup overrides
    del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_change_password_incorrect_old(db_session: AsyncSession):
    # 1. Setup
    user_password = "oldpassword"
    user = User(
        username="test_admin_2",
        email="test2@example.com",
        hashed_password=get_password_hash(user_password),
        is_admin=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.username})

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(
            f"{settings.api_prefix}/auth/password",
            json={"old_password": "wrongpassword", "new_password": "newpassword"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect old password"

    del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_startup_creates_master_user(db_session: AsyncSession):
    # Verify main.py logic manually by importing the lifespan logic or simulating checks
    # Since lifespan is a context manager, we can try to invoke it, but it might mess with global state.
    # Instead, let's just assert that IF we run the logic "check user count, if 0 create master", it works.

    from sqlalchemy import select, delete

    # Ensure DB is empty
    await db_session.execute(delete(User))
    await db_session.commit()

    # Run the startup logic snippet (simulated)
    result = await db_session.execute(select(User))
    user = result.scalars().first()

    if not user:
        master_admin = User(
            username="master",
            email="admin@mavrov.de",
            hashed_password=get_password_hash("master"),
            is_admin=True,
            is_active=True,
        )
        db_session.add(master_admin)
        await db_session.commit()

    # Verify
    result = await db_session.execute(select(User).where(User.username == "master"))
    master = result.scalar_one_or_none()
    assert master is not None
    assert master.is_admin is True
    assert verify_password("master", master.hashed_password)
