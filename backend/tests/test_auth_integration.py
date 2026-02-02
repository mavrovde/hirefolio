import pytest
from fastapi import HTTPException
from app.services.auth import (
    get_current_user,
    get_current_user_optional,
    get_current_admin_user,
    create_access_token,
)
from app.models.user import User


@pytest.mark.asyncio
async def test_get_current_user_success(db_session):
    # Create a user
    user = User(
        username="testuser",
        email="test@test.com",
        hashed_password="hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token({"sub": "testuser"})
    retrieved_user = await get_current_user(token=token, db=db_session)
    assert retrieved_user.username == "testuser"


@pytest.mark.asyncio
async def test_get_current_user_not_found(db_session):
    token = create_access_token({"sub": "nonexistent"})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_inactive(db_session):
    user = User(
        username="inactive", email="i@test.com", hashed_password="hash", is_active=False
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "inactive"})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=db_session)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_current_user_no_sub(db_session):
    token = create_access_token({})  # Empty payload, no sub
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token="invalid", db=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_optional_present(db_session):
    user = User(
        username="opt", email="opt@test.com", hashed_password="hash", is_active=True
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "opt"})
    retrieved_user = await get_current_user_optional(token=token, db=db_session)
    assert retrieved_user.username == "opt"


@pytest.mark.asyncio
async def test_get_current_user_optional_missing(db_session):
    retrieved_user = await get_current_user_optional(token=None, db=db_session)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_get_current_user_optional_invalid_token(db_session):
    retrieved_user = await get_current_user_optional(token="invalid", db=db_session)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_get_current_user_optional_no_sub(db_session):
    token = create_access_token({})  # Empty payload, no sub
    retrieved_user = await get_current_user_optional(token=token, db=db_session)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_get_current_user_optional_user_not_found(db_session):
    token = create_access_token({"sub": "nonexistent"})
    retrieved_user = await get_current_user_optional(token=token, db=db_session)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_get_current_admin_user_success():
    admin = User(username="admin", is_admin=True)
    retrieved = await get_current_admin_user(current_user=admin)
    assert retrieved.username == "admin"


@pytest.mark.asyncio
async def test_get_current_admin_user_forbidden():
    user = User(username="user", is_admin=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_admin_user(current_user=user)
    assert exc.value.status_code == 403
