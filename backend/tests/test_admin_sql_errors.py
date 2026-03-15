import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient


# Remove list_tables test as endpoint doesn't exist in admin_sql.py


@pytest.mark.asyncio
async def test_admin_sql_execute_error(client: AsyncClient, admin_token_headers):
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        side_effect=Exception("Query Error"),
    ):
        resp = await client.post(
            "/api/app/admin/sql/execute",
            json={"query": "SELECT *"},
            headers=admin_token_headers,
        )
        assert resp.status_code == 400
        assert "SQL Execution Error" in resp.text


@pytest.mark.asyncio
async def test_admin_sql_backup_error(client: AsyncClient, admin_token_headers):
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        resp = await client.get(
            "/api/app/admin/sql/backup", headers=admin_token_headers
        )
        assert resp.status_code == 500
        assert "pg_dump not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_sql_restore_errors(client: AsyncClient, admin_token_headers):
    files = {"file": ("backup.sql", b"SQL DUMP", "text/plain")}

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Restore Error"))
    mock_proc.returncode = 1
    mock_proc.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        resp = await client.post(
            "/api/app/admin/sql/restore", files=files, headers=admin_token_headers
        )
        assert resp.status_code == 500
        assert "Restore failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_sql_restore_invalid_extension(
    client: AsyncClient, admin_token_headers
):
    files = {"file": ("backup.txt", b"SQL DUMP", "text/plain")}
    resp = await client.post(
        "/api/app/admin/sql/restore", files=files, headers=admin_token_headers
    )
    assert resp.status_code == 400
    assert "Only .sql files" in resp.json()["detail"]
