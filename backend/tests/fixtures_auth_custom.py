import pytest
from app.services.auth import create_access_token
from app.models.user import User
from app.services.auth import get_password_hash


@pytest.fixture(scope="function")
async def admin_user(db_session):
    # Check if admin exists
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.username == "admin"))
    user = result.scalars().first()
    if not user:
        user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin"),
            is_admin=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
    return user


@pytest.fixture(scope="function")
def admin_token_headers(admin_user):
    access_token = create_access_token(data={"sub": admin_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
async def normal_user(db_session):
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.username == "user"))
    user = result.scalars().first()
    if not user:
        user = User(
            username="user",
            email="user@example.com",
            hashed_password=get_password_hash("user"),
            is_admin=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
    return user


@pytest.fixture(scope="function")
def normal_user_token_headers(normal_user):
    access_token = create_access_token(data={"sub": normal_user.username})
    return {"Authorization": f"Bearer {access_token}"}
