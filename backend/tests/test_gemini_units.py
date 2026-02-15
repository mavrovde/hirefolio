
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.ai import _get_gemini_client
from app.api.auth import update_gemini_key, UpdateGeminiKeyRequest
from app.models.user import User

# Unit tests do not need DB interaction if we mock everything
# This ensures lines are hit logic-wise without integration setup


def test_get_gemini_client_with_user_key():
    with patch("app.services.ai.genai", create=True) as mock_genai:
        with patch("app.services.ai.HAS_GEMINI", True):
            client = _get_gemini_client(user_api_key="test-key")
            assert client is not None
            mock_genai.Client.assert_called_with(api_key="test-key")

def test_get_gemini_client_no_key_no_env():
    with patch("app.services.ai.HAS_GEMINI", True):
        # mocking settings to have no key
        with patch("app.services.ai.settings") as mock_settings:
            mock_settings.gemini_api_key = ""
            client = _get_gemini_client(user_api_key=None)
            assert client is None

def test_get_gemini_client_fallback_env():
    with patch("app.services.ai.genai", create=True) as mock_genai:
        with patch("app.services.ai.HAS_GEMINI", True):
            with patch("app.services.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "env-key"
                client = _get_gemini_client(user_api_key=None)
                assert client is not None
                mock_genai.Client.assert_called_with(api_key="env-key")

@pytest.mark.asyncio
async def test_auth_update_gemini_key_unit():
    # Mock dependencies
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.username = "test"
    mock_user.email = "test@test.com"
    mock_user.is_admin = True
    mock_user.gemini_api_key = "old"

    key_data = UpdateGeminiKeyRequest(api_key="new-key")

    response = await update_gemini_key(
        key_data=key_data,
        current_user=mock_user,
        db=mock_db
    )

    assert mock_user.gemini_api_key == "new-key"
    mock_db.add.assert_called_with(mock_user)
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(mock_user)
    
    assert response.gemini_api_key == "new-key"
