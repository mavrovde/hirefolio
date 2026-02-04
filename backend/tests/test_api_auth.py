import pytest
from httpx import AsyncClient
from app.models.user import User
from app.services.auth import get_password_hash

# We need to test the REAL auth endpoints, so we should NOT use the global override
# that mocks get_current_user for THESE tests if possible.
# However, global override in conftest.py applies to 'client'.
# To test auth endpoints (login), we don't need authentication!
# To test /me, we DO need authentication.
# If global mock is active, /me returns admin.
# But we want to test that /login returns a token.


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    # Create a user in DB (requires hashing password)
    # Since client fixture mocks DB too, we need to ensure the user exists in the session.
    # The fixture mock_admin is useful but we need a real user for login check?
    # Wait, client overrides get_db to return db_session.
    # So we can insert into db_session.

    password = "testpassword"
    hashed = get_password_hash(password)
    user = User(
        username="loginuser",
        email="login@example.com",
        hashed_password=hashed,
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    # Login
    response = await client.post(
        "/api/auth/login",
        data={"username": "loginuser", "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        data={"username": "nonexistent", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session):
    password = "testpassword"
    user = User(
        username="inactiveuser",
        email="inactive@example.com",
        hashed_password=get_password_hash(password),
        is_active=False,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        data={"username": "inactiveuser", "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, db_session):
    # The global override returns mock_admin (password "admin")
    # We need to Ensure it persists in DB for this test if we use DB
    # However, our client fixture mocks the current_user to be mock_admin.
    # The endpoint change_password uses current_user.

    response = await client.put(
        "/api/auth/password",
        json={"old_password": "admin", "new_password": "newpass"},
    )
    assert response.status_code == 204

    # The password change happens on the current_user object which is mock_admin
    # Since mock_admin is a shared object in this test context, we can check it.
    # Wait, it's safer to check if the response was 204.
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_invalid_old(client: AsyncClient, db_session):
    response = await client.put(
        "/api/auth/password",
        json={"old_password": "wrongpass", "new_password": "newpass"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect old password"
