import json
from unittest.mock import patch

import pytest

from app.services.chat import chat_with_llm


class MockHttpxClient:
    def __init__(self, mode="success"):
        self.mode = mode

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def stream(self, method, url, **kwargs):
        if self.mode == "error":
            raise Exception("Network failure")
        return MockStreamContext(self.mode)


class MockStreamContext:
    def __init__(self, mode):
        self.mode = mode

    async def __aenter__(self):
        return MockResponse(self.mode)

    async def __aexit__(self, exc_type, exc, tb):
        pass


class MockResponse:
    def __init__(self, mode):
        self.mode = mode

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        if self.mode == "success":
            fake_lines = [
                json.dumps({"message": {"content": "Hello"}, "done": False}),
                json.dumps({"message": {"content": "!"}, "done": True}),
            ]
        elif self.mode == "invalid_json":
            fake_lines = [
                "{invalid}",
                json.dumps({"message": {"content": "Ok"}, "done": True}),
            ]
        else:
            fake_lines = []

        for line in fake_lines:
            yield line


@pytest.mark.asyncio
async def test_chat_with_llm_success():
    with patch(
        "httpx.AsyncClient", side_effect=lambda **kw: MockHttpxClient("success")
    ):
        chunks = [c async for c in chat_with_llm([{"role": "user", "content": "hi"}])]
    assert chunks == ["Hello", "!"]


@pytest.mark.asyncio
async def test_chat_with_llm_invalid_json():
    with patch(
        "httpx.AsyncClient", side_effect=lambda **kw: MockHttpxClient("invalid_json")
    ):
        chunks = [c async for c in chat_with_llm([])]
    # Should skip invalid line and yield correct one
    assert "Ok" in chunks


@pytest.mark.asyncio
async def test_chat_with_llm_exception():
    with patch("httpx.AsyncClient", side_effect=lambda **kw: MockHttpxClient("error")):
        chunks = [c async for c in chat_with_llm([])]
    assert any("System Error" in c for c in chunks)


@pytest.mark.asyncio
async def test_chat_with_llm_with_stop_sequences():
    with patch(
        "httpx.AsyncClient", side_effect=lambda **kw: MockHttpxClient("success")
    ):
        chunks = [
            c
            async for c in chat_with_llm(
                [{"role": "user", "content": "hi"}], stop_sequences=["\n"]
            )
        ]
    assert chunks == ["Hello", "!"]
