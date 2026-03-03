import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.linkedin import LinkedInService
from app.config import settings

@pytest.fixture
def linkedin_svc():
    return LinkedInService()

@pytest.mark.asyncio
async def test_run_scraper_missing_credentials(linkedin_svc):
    with patch("app.services.linkedin.settings.linkedin_email", ""), \
         patch("app.services.linkedin.settings.linkedin_password", ""):
        with pytest.raises(ValueError, match="LinkedIn credentials are not configured"):
            await linkedin_svc._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_process_error(linkedin_svc):
    with patch("app.services.linkedin.settings.linkedin_email", "test@test.com"), \
         patch("app.services.linkedin.settings.linkedin_password", "pw"):
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Error message")
        mock_process.returncode = 1
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="LinkedIn scraper failed: Error message"):
                 await linkedin_svc._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_missing_output_file(linkedin_svc):
    with patch("app.services.linkedin.settings.linkedin_email", "test@test.com"), \
         patch("app.services.linkedin.settings.linkedin_password", "pw"):
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
             patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Scraper output file not found"):
                 await linkedin_svc._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_invalid_json(linkedin_svc):
    with patch("app.services.linkedin.settings.linkedin_email", "test@test.com"), \
         patch("app.services.linkedin.settings.linkedin_password", "pw"):
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", side_effect=json.JSONDecodeError("msg", "doc", 0)):
            with pytest.raises(ValueError, match="Invalid JSON returned from scraper"):
                 await linkedin_svc._run_scraper("script.js", "out.json")

@pytest.mark.asyncio
async def test_run_scraper_success(linkedin_svc):
    with patch("app.services.linkedin.settings.linkedin_email", "test@test.com"), \
         patch("app.services.linkedin.settings.linkedin_password", "pw"):
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        
        expected_data = {"key": "value"}
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value=expected_data):
            
            result = await linkedin_svc._run_scraper("script.js", "out.json")
            assert result == expected_data

@pytest.mark.asyncio
async def test_fetch_posts_success(linkedin_svc):
    with patch.object(linkedin_svc, "_run_scraper", return_value=[{"id": 1}]):
        result = await linkedin_svc.fetch_posts()
        assert result == [{"id": 1}]

@pytest.mark.asyncio
async def test_fetch_posts_not_list(linkedin_svc):
    with patch.object(linkedin_svc, "_run_scraper", return_value={"id": 1}):
        result = await linkedin_svc.fetch_posts()
        assert result == []

@pytest.mark.asyncio
async def test_sync_profile_success(linkedin_svc):
    expected_profile = {"name": "Test"}
    with patch.object(linkedin_svc, "_run_scraper", return_value=expected_profile):
        result = await linkedin_svc.sync_profile()
        assert result == expected_profile
