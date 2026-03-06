import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app

from app.config import settings


@pytest.fixture
async def unauthed_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_backup_database_unauthorized(unauthed_client: AsyncClient):
    response = await unauthed_client.get(f"{settings.api_prefix}/admin/sql/backup")
    assert response.status_code in [401, 403]


def _make_async_proc(
    stdout_data: list[bytes], returncode: int = 0, stderr_data: bytes = b""
):
    """Helper to create a mock async subprocess process."""
    mock_proc = AsyncMock()
    mock_proc.returncode = returncode

    # stdout.read returns chunks then empty
    mock_proc.stdout = AsyncMock()
    mock_proc.stdout.read = AsyncMock(side_effect=stdout_data)

    # stderr.read returns error data
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=stderr_data)

    # communicate returns (stdout, stderr)
    combined_stdout = b"".join(d for d in stdout_data if d)
    mock_proc.communicate = AsyncMock(return_value=(combined_stdout, stderr_data))

    # terminate/kill
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()

    return mock_proc


@pytest.mark.asyncio
async def test_backup_database_success(client: AsyncClient):
    mock_proc = _make_async_proc([b"dump_chunk_1", b"dump_chunk_2", b""], returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = await client.get(f"{settings.api_prefix}/admin/sql/backup")

        assert response.status_code == 200
        assert "application/sql" in response.headers["content-type"]
        assert (
            "attachment; filename=backup_mavrov_"
            in response.headers["content-disposition"]
        )
        assert b"dump_chunk_1dump_chunk_2" in response.content


@pytest.mark.asyncio
async def test_backup_database_failure(client: AsyncClient):
    mock_proc = _make_async_proc([b""], returncode=1, stderr_data=b"pg_dump error")
    mock_proc.wait = AsyncMock(return_value=1)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = await client.get(f"{settings.api_prefix}/admin/sql/backup")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_restore_database_unauthorized(unauthed_client: AsyncClient):
    response = await unauthed_client.post(
        f"{settings.api_prefix}/admin/sql/restore",
        files={"file": ("dump.sql", b"content")},
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_restore_database_invalid_file(client: AsyncClient):
    response = await client.post(
        f"{settings.api_prefix}/admin/sql/restore",
        files={"file": ("dump.txt", b"content")},
    )
    assert response.status_code == 400
    assert "Only .sql files are allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_restore_database_success(client: AsyncClient):
    mock_proc = _make_async_proc([b"restore output"], returncode=0)
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = await client.post(
            f"{settings.api_prefix}/admin/sql/restore",
            files={"file": ("backup.sql", b"sql content")},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Database restored successfully"


@pytest.mark.asyncio
async def test_restore_database_failure(client: AsyncClient):
    mock_proc = _make_async_proc([], returncode=1, stderr_data=b"psql error")
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = await client.post(
            f"{settings.api_prefix}/admin/sql/restore",
            files={"file": ("backup.sql", b"sql content")},
        )

        assert response.status_code == 500
        assert "Restore failed" in response.json()["detail"]
