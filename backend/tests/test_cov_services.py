"""Targeted coverage tests for app.services.{ai,chat,linkedin}.

Covers previously-uncovered branches:
- chat.py 33->exit  (aiter_lines exhausts with no `done` flag)
- chat.py 34->33     (an empty streamed line is skipped)
- linkedin.py 177->181 (commentary is neither dict nor str)
- linkedin.py 187->193 (raw["content"] is not a dict, nested-article path skipped)
- linkedin.py 194->205 (raw["content"] is not a dict, image path skipped)
"""

import json
from unittest.mock import patch

import pytest

from app.services.chat import chat_with_llm
from app.services.linkedin import LinkedInService

# --------------------------------------------------------------------------
# chat.py stream branches
# --------------------------------------------------------------------------


class _StreamResponse:
    """Fake httpx streaming response emitting a fixed set of lines."""

    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamCtx:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return _StreamResponse(self._lines)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _AsyncClient:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, **kwargs):
        return _StreamCtx(self._lines)


@pytest.mark.asyncio
async def test_chat_with_llm_empty_line_and_no_done():
    """An empty line is skipped (34->33) and the loop exhausts without a
    `done` flag, exiting the for-loop naturally (33->exit)."""
    lines = [
        "",  # empty -> `if line:` false, loop back (34->33)
        json.dumps({"message": {"content": "part1"}, "done": False}),
        json.dumps({"message": {"content": "part2"}, "done": False}),
        # no line sets done=True, so aiter_lines exhausts (33->exit)
    ]

    with patch("httpx.AsyncClient", side_effect=lambda **kw: _AsyncClient(lines)):
        chunks = [c async for c in chat_with_llm([{"role": "user", "content": "hi"}])]

    # Empty line skipped; both content chunks yielded; no error appended.
    assert chunks == ["part1", "part2"]


# --------------------------------------------------------------------------
# linkedin.py _parse_post branches
# --------------------------------------------------------------------------


def test_parse_post_commentary_non_dict_non_str_and_content_non_dict():
    """commentary is a list (neither dict nor str -> 177->181), and
    raw['content'] is a list (not a dict -> 187->193 and 194->205).
    With no usable text the parser returns None."""
    post = LinkedInService._parse_post(
        {
            "commentary": ["not", "a", "dict-or-str"],
            "content": ["not", "a", "dict"],
            "updateMetadata": {"urn": "urn:li:activity:999"},
        }
    )
    assert post is None
