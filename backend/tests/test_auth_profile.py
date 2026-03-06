
import pytest
from httpx import AsyncClient
from app.services.auth import verify_password
from app.models.user import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_change_password_success(clean_client: AsyncClient, admin_token_headers, db_session):
    # Setup: ensure admin has expected password "admin"
    admin_headers = admin_token_headers
    
    # Change password
    new_password = "newsecurepassword123"
    response = await clean_client.put(
        "/api/app/auth/password",
        headers=admin_headers,
        json={"old_password": "admin", "new_password": new_password}
    )
    assert response.status_code == 204

    # Verify implementation: check DB
    result = await db_session.execute(select(User).where(User.username == "admin"))
    user = result.scalars().first()
    assert verify_password(new_password, user.hashed_password)

    # Revert password for other tests
    # Reset to "admin" hash
    # Note: We need to be careful if db_session transaction is isolated.
    # Ideally tests should clean up.
    user.hashed_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW" 
    db_session.add(user)
    await db_session.commit()

@pytest.mark.asyncio
async def test_change_password_wrong_old_password(clean_client: AsyncClient, admin_token_headers):
    response = await clean_client.put(
        "/api/app/auth/password",
        headers=admin_token_headers,
        json={"old_password": "wrongpassword", "new_password": "newpass"}
    )
    assert response.status_code == 400
    assert "Incorrect old password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_change_password_unauthorized(clean_client: AsyncClient):
    # No headers -> unauthorized
    response = await clean_client.put(
        "/api/app/auth/password",
        json={"old_password": "admin", "new_password": "newpass"}
    )
    assert response.status_code == 401
