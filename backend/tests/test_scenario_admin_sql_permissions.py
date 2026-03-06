import pytest
from httpx import AsyncClient
from app.config import settings

@pytest.mark.asyncio
async def test_admin_sql_execute_forbidden(clean_client: AsyncClient, normal_user_token_headers):
    """Test SQL execution with non-admin user returns 403."""
    response = await clean_client.post(
        f"{settings.api_prefix}/admin/sql/execute",
        headers=normal_user_token_headers,
        json={"query": "SELECT * FROM users"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

@pytest.mark.asyncio
async def test_admin_sql_backup_forbidden(clean_client: AsyncClient, normal_user_token_headers):
    """Test backup with non-admin user returns 403."""
    response = await clean_client.get(
        f"{settings.api_prefix}/admin/sql/backup",
        headers=normal_user_token_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

@pytest.mark.asyncio
async def test_admin_sql_restore_forbidden(clean_client: AsyncClient, normal_user_token_headers):
    """Test restore with non-admin user returns 403."""
    # We need to simulate file upload even if it's forbidden, to hit the endpoint logic
    response = await clean_client.post(
        f"{settings.api_prefix}/admin/sql/restore",
        headers=normal_user_token_headers,
        files={"file": ("backup.sql", b"content", "application/sql")}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

@pytest.mark.asyncio
async def test_admin_sql_execute_commit_path(client: AsyncClient, admin_token_headers):
    """Test SQL execution for non-SELECT query (commit path)."""
    # We can use a harmless UPDATE or INSERT on a test table or rollback transaction if possible.
    # But since we use a shared database in tests, ideally we shouldn't break data.
    # We can try to UPDATE the admin user's updated_at timestamp or similar innocuous change.
    
    # Or creating a temporary table?
    # Let's try updating the current user (admin)
    query = "UPDATE users SET is_active = true WHERE email = 'admin@example.com'"
    
    response = await client.post(
        f"{settings.api_prefix}/admin/sql/execute",
        headers=admin_token_headers,
        json={"query": query}
    )
    assert response.status_code == 200
    data = response.json()
    # Expect [{"message": ..., "duration_ms": ...}]
    assert isinstance(data, list)
    assert len(data) == 1
    assert "message" in data[0]
    assert data[0]["message"] == "Query executed successfully"
