from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


@patch("app.api.ai.chat_with_llm")
def test_chat_endpoint(mock_chat_service):
    # Mock the generator to yield data immediately
    async def mock_generator(messages):
        yield "AI Response"

    mock_chat_service.side_effect = mock_generator

    response = client.post(
        "/api/ai/chat", json={"messages": [{"role": "user", "content": "hello"}]}
    )

    assert response.status_code == 200
    assert "AI Response" in response.text
