import pytest
import asyncio
import json
import os
from unittest.mock import MagicMock
from app.services.linkedin import LinkedInService

@pytest.fixture
def service():
    return LinkedInService()

@pytest.mark.asyncio
async def test_run_scraper_missing_credentials(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "")

    with pytest.raises(ValueError, match="LinkedIn credentials are not configured"):
        await service._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_subprocess_failure(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    class MockProcess:
        returncode = 1
        async def communicate(self):
            return b"", b"Fatal node error"

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())

    with pytest.raises(RuntimeError, match="LinkedIn scraper failed: Fatal node error"):
        await service._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_timeout(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    class MockProcess:
        returncode = None
        def kill(self):
            pass
        async def wait(self):
            pass
        async def communicate(self):
            raise asyncio.TimeoutError()

    async def mock_communicate():
        raise asyncio.TimeoutError()

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())
    mocker.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError)

    with pytest.raises(RuntimeError, match="LinkedIn scraper timed out"):
        await service._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_file_not_found(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    class MockProcess:
        returncode = 0
        async def communicate(self):
            return b"success", b""

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())
    async def mock_wait_for(coro, timeout):
        return await coro
    mocker.patch("asyncio.wait_for", side_effect=mock_wait_for)
    mocker.patch("app.services.linkedin.os.path.exists", return_value=False)

    with pytest.raises(FileNotFoundError, match="Scraper output file not found"):
        await service._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_invalid_json(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    class MockProcess:
        returncode = 0
        async def communicate(self):
            return b"", b""

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())
    async def mock_wait_for(coro, timeout):
        return await coro
    mocker.patch("asyncio.wait_for", side_effect=mock_wait_for)
    mocker.patch("app.services.linkedin.os.path.exists", return_value=True)

    mocker.patch("builtins.open", mocker.mock_open(read_data="invalid json"))

    with pytest.raises(ValueError, match="Invalid JSON returned from scraper"):
        await service._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_success(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    class MockProcess:
        returncode = 0
        async def communicate(self):
            return b"", b""

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())
    async def mock_wait_for(coro, timeout):
        return await coro
    mocker.patch("asyncio.wait_for", side_effect=mock_wait_for)
    mocker.patch("app.services.linkedin.os.path.exists", return_value=True)

    mocker.patch("builtins.open", mocker.mock_open(read_data='{"status": "ok"}'))

    result = await service._run_scraper("script.js", "out.json")
    assert result == {"status": "ok"}

@pytest.mark.asyncio
async def test_fetch_posts_success(service, mocker):
    mocker.patch.object(service, "_run_scraper", return_value=[{"post": 1}])
    posts = await service.fetch_posts()
    assert posts == [{"post": 1}]

@pytest.mark.asyncio
async def test_fetch_posts_invalid_return_type(service, mocker):
    mocker.patch.object(service, "_run_scraper", return_value={"error": "not a list"})
    posts = await service.fetch_posts()
    assert posts == []

@pytest.mark.asyncio
async def test_sync_profile_success(service, mocker):
    mocker.patch.object(service, "_run_scraper", return_value={"profile": "data"})
    profile = await service.sync_profile()
    assert profile == {"profile": "data"}
