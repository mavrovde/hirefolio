"""Tests for AI API endpoints (avatar and dual-chat)."""

import json
from unittest.mock import patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app as fastapi_app


@pytest.mark.asyncio
async def test_generate_name_endpoint():
    """Test name generation endpoint."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mocking the internal chat function is tricky without patching app.api.ai.chat_with_llm
        # But for integration test we can mock lower level or just check structure if we want real LLM (not recommended)
        # Better to patch _generate_agent_name or chat_with_llm
        with patch("app.api.ai.chat_with_llm") as mock_chat:
            # Mock generator
            async def mock_generator(messages):
                yield "Agent Name"

            mock_chat.side_effect = mock_generator

            response = await client.post(
                "/api/ai/generate-name", json={"description": "A cool spy"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "name" in data
            assert data["name"] == "Agent Name"


@pytest.mark.asyncio
async def test_multi_chat_endpoint_success():
    """Test the multi-chat endpoint."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "agents": [
                {"id": 1, "name": "A1", "description": "D1"},
                {"id": 2, "name": "A2", "description": "D2"},
            ],
            "topic": "Test Topic",
        }

        async def mock_gen(*args, **kwargs):
            yield json.dumps({"agent": 1, "content": "Hello"}) + "\n"
            yield (
                json.dumps({"agent": 1, "content": " World", "turn_complete": True})
                + "\n"
            )

        with patch("app.api.ai.multi_agent_conversation", side_effect=mock_gen):
            response = await client.post("/api/ai/multi-chat", json=payload)
            assert response.status_code == 200
            content = response.content.decode()
            assert "Hello" in content
            assert "World" in content
