from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_chat_stream():
    async def stream_gen(messages):
        yield "Hello"
        yield " World"

    return stream_gen


@pytest.mark.asyncio
async def test_chat_endpoint(client: AsyncClient, mock_chat_stream):
    with patch("app.api.ai.chat_with_llm", side_effect=mock_chat_stream):
        resp = await client.post(
            "/api/app/ai/chat", json={"messages": [{"role": "user", "content": "Hi"}]}
        )
        assert resp.status_code == 200
        # Streaming response is hard to verify content directly in httpx without iterating
        # But 200 OK means it started.


@pytest.mark.asyncio
async def test_gemini_chat_endpoint(client: AsyncClient):
    with patch("app.services.ai.chat_with_gemini", return_value="Gemini Response"):
        resp = await client.post(
            "/api/app/ai/gemini-chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["response"] == "Gemini Response"


@pytest.mark.asyncio
async def test_generate_name_endpoint(client: AsyncClient, mock_chat_stream):
    # Test successful generation
    with patch("app.api.ai.chat_with_llm", side_effect=mock_chat_stream):
        resp = await client.post(
            "/api/app/ai/generate-name", json={"description": "A cool agent"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Hello World"

    # Test error fallback
    with patch("app.api.ai.chat_with_llm", side_effect=Exception("LLM Error")):
        resp = await client.post(
            "/api/app/ai/generate-name", json={"description": "A cool agent"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Agent"


@pytest.mark.asyncio
async def test_multi_chat_endpoint(client: AsyncClient):
    async def mock_multi_stream(agents, topic):
        yield "Agent1: Hi"

    with patch("app.api.ai.multi_agent_conversation", side_effect=mock_multi_stream):
        resp = await client.post(
            "/api/app/ai/multi-chat",
            json={
                "agents": [
                    {
                        "id": 1,
                        "name": "A1",
                        "role": "R1",
                        "description": "P1",
                        "goal": "G1",
                    }
                ],
                "topic": "Topic",
            },
        )
        assert resp.status_code == 200
