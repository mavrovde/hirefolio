import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.admin_sql import execute_sql, SqlQuery
from fastapi import HTTPException

# Tests for missing branches in admin_sql.py

@pytest.mark.asyncio
async def test_admin_sql_execute_invalid_query_type(client: AsyncClient, db_session: AsyncSession):
    # Test execution involving unsupported query type by mocking db.execute to raise Exception
    # We mock the session instance directly since it's injected via dependency override
    
    # Create a side_effect that raises exception
    # Need to verify if execute is a coroutine or returns awaitable
    # AsyncSession.execute is awaitable.
    
    # We can wrap the original execute or just replace it.
    # But we only want it to fail for THIS call.
    with patch.object(db_session, 'execute', side_effect=Exception("DB Error")):
        response = await client.post(
            "/api/app/admin/sql/execute",
            json={"query": "SELECT * FROM users"}
        )
        assert response.status_code == 400
        assert "SQL Execution Error" in response.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_backup_error(client: AsyncClient):
    # Test error during backup streaming (lines 111-112)
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = Exception("Stream Error")
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        
        response = await client.get("/api/app/admin/sql/backup")
        
        # The response will start streaming but fail mid-way. 
        try:
            async for _ in response.aiter_bytes():
                pass
        except Exception:
            pass
        
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_admin_sql_backup_pg_dump_not_found(client: AsyncClient):
    # Test pg_dump not found (lines 93-94)
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.side_effect = FileNotFoundError()
        
        response = await client.get("/api/app/admin/sql/backup")
        assert response.status_code == 500
        assert "pg_dump not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_restore_psql_not_found(client: AsyncClient):
    # Test psql not found (lines 167-168)
    files = {"file": ("backup.sql", "SQL CONTENT", "application/sql")}
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.side_effect = FileNotFoundError()
        
        response = await client.post("/api/app/admin/sql/restore", files=files)
        assert response.status_code == 500
        assert "psql not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_admin_sql_restore_generic_error(client: AsyncClient):
    # Test generic error/exception (lines 169-170)
    files = {"file": ("backup.sql", "SQL CONTENT", "application/sql")}
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.side_effect = Exception("Random Error")
        
        response = await client.post("/api/app/admin/sql/restore", files=files)
        assert response.status_code == 500
        assert "Restore error" in response.json()["detail"]

