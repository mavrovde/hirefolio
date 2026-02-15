
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from tests.fixtures_auth_custom import admin_token_headers, admin_user

from sqlalchemy.ext.asyncio import AsyncSession

# Remove list_tables test as endpoint doesn't exist in admin_sql.py

@pytest.mark.asyncio
async def test_admin_sql_execute_error(client: AsyncClient, admin_token_headers):
    # Patch AsyncSession.execute globally or on the session
    # Since we don't have easy access to the exact session object instance inside the route handler
    # without the fixture, we can patch the class or use side_effect on the db_session fixture if passed.
    # Let's patch the class method for simplicity in this error case.
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=Exception("Query Error")):
        # Endpoint is /execute, not /query
        resp = await client.post("/api/app/admin/sql/execute", json={"query": "SELECT *"}, headers=admin_token_headers)
        # The exception handler in admin_sql.py catches Exception and raises 400
        assert resp.status_code == 400
        assert "Query Error" in resp.json()["detail"]
        assert "SQL Execution Error" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_backup_error(client: AsyncClient, admin_token_headers):
    # Patch subprocess.Popen globally since it is imported inside the function
    with patch("subprocess.Popen", side_effect=FileNotFoundError):
        resp = await client.get("/api/app/admin/sql/backup", headers=admin_token_headers)
        assert resp.status_code == 500
        assert "pg_dump not found" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_restore_errors(client: AsyncClient, admin_token_headers):
    # Test valid extension but subprocess fail
    files = {"file": ("backup.sql", b"SQL DUMP", "text/plain")}
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"Restore Error")
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc
        
        resp = await client.post("/api/app/admin/sql/restore", files=files, headers=admin_token_headers)
        assert resp.status_code == 500
        assert "Restore failed" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_restore_invalid_extension(client: AsyncClient, admin_token_headers):
    files = {"file": ("backup.txt", b"SQL DUMP", "text/plain")}
    resp = await client.post("/api/app/admin/sql/restore", files=files, headers=admin_token_headers)
    assert resp.status_code == 400
    assert "Only .sql files" in resp.json()["detail"]
