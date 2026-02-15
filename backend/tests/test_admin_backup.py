import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app

from app.config import settings

@pytest.fixture
async def unauthed_client():
    from app.services.auth import get_current_admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_backup_database_unauthorized(unauthed_client: AsyncClient):
    response = await unauthed_client.get(f"{settings.api_prefix}/admin/sql/backup")
    assert response.status_code in [401, 403]

@pytest.mark.asyncio
async def test_backup_database_success(client: AsyncClient):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [b"dump_chunk_1", b"dump_chunk_2", b""]
        mock_process.wait.return_value = 0
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        response = await client.get(f"{settings.api_prefix}/admin/sql/backup")
        
        assert response.status_code == 200
        assert "application/sql" in response.headers["content-type"]
        assert "attachment; filename=backup_mavrov_" in response.headers["content-disposition"]
        assert b"dump_chunk_1dump_chunk_2" in response.content

@pytest.mark.asyncio
async def test_backup_database_failure(client: AsyncClient):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = b""
        mock_process.wait.return_value = 1
        mock_process.stderr.read.return_value = b"pg_dump error"
        mock_popen.return_value = mock_process
        
        response = await client.get(f"{settings.api_prefix}/admin/sql/backup")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_restore_database_unauthorized(unauthed_client: AsyncClient):
    response = await unauthed_client.post(
        f"{settings.api_prefix}/admin/sql/restore", 
        files={"file": ("dump.sql", b"content")}
    )
    assert response.status_code in [401, 403]

@pytest.mark.asyncio
async def test_restore_database_invalid_file(client: AsyncClient):
    response = await client.post(
        f"{settings.api_prefix}/admin/sql/restore", 
        files={"file": ("dump.txt", b"content")}
    )
    assert response.status_code == 400
    assert "Only .sql files are allowed" in response.json()["detail"]

@pytest.mark.asyncio
async def test_restore_database_success(client: AsyncClient):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"restore output", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        response = await client.post(
            f"{settings.api_prefix}/admin/sql/restore", 
            files={"file": ("backup.sql", b"sql content")}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Database restored successfully"

@pytest.mark.asyncio
async def test_restore_database_failure(client: AsyncClient):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"psql error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        response = await client.post(
            f"{settings.api_prefix}/admin/sql/restore", 
            files={"file": ("backup.sql", b"sql content")}
        )
        
        assert response.status_code == 500
        assert "Restore failed" in response.json()["detail"]
