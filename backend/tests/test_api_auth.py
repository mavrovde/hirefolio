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
        is_admin=False
    )
    db_session.add(user)
    await db_session.commit()
    
    # Login
    response = await client.post(
        "/api/auth/login", 
        data={"username": "loginuser", "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
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
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    # This uses the global override which returns mock_admin
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["email"] == "admin@example.com"
