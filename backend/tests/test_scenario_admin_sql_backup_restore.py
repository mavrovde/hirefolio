import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# Tests for missing branches in admin_sql.py


@pytest.mark.asyncio
async def test_admin_sql_execute_invalid_query_type(
    client: AsyncClient, db_session: AsyncSession
):
    with patch.object(db_session, "execute", side_effect=Exception("DB Error")):
        response = await client.post(
            "/api/app/admin/sql/execute", json={"query": "SELECT * FROM users"}
        )
        assert response.status_code == 501
        assert "SQL Execution Error" in response.text


@pytest.mark.asyncio
async def test_admin_sql_backup_error(client: AsyncClient):
    # Test error during backup streaming
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.stdout = AsyncMock()
    mock_proc.stdout.read = AsyncMock(side_effect=Exception("Stream Error"))
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=b"")
    mock_proc.terminate = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = await client.get("/api/app/admin/sql/backup")

        # Response starts streaming but fails mid-way
        try:
            async for _ in response.aiter_bytes():
                pass
        except Exception:
            pass

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_sql_backup_pg_dump_not_found(client: AsyncClient):
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
        response = await client.get("/api/app/admin/sql/backup")
        assert response.status_code == 500
        assert "pg_dump not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_sql_restore_psql_not_found(client: AsyncClient):
    files = {"file": ("backup.sql", "SQL CONTENT", "application/sql")}
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
        response = await client.post("/api/app/admin/sql/restore", files=files)
        assert response.status_code == 500
        assert "psql not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_sql_restore_generic_error(client: AsyncClient):
    files = {"file": ("backup.sql", "SQL CONTENT", "application/sql")}
    with patch(
        "asyncio.create_subprocess_exec", side_effect=RuntimeError("Random Error")
    ):
        response = await client.post("/api/app/admin/sql/restore", files=files)
        assert response.status_code == 500
        assert "Restore error" in response.json()["detail"]
