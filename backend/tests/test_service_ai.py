import pytest
import respx
from unittest.mock import patch
from httpx import Response
from app.services.ai import suggest_tags, suggest_post_details, suggest_field
from app.config import settings


@pytest.mark.asyncio
async def test_suggest_tags_valid_json():
    """Test AI service with valid JSON response from Ollama."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '["angular", "typescript", "web-dev"]'}
            )
        )

        tags = await suggest_tags("Title", "Content")
        assert tags == ["angular", "typescript", "web-dev"]


@pytest.mark.asyncio
async def test_suggest_tags_wrapped_json():
    """Test AI service with JSON wrapped in a dict object."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '{"tags": ["python", "fastapi"]}'}
            )
        )

        tags = await suggest_tags("Title", "Content")
        assert tags == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_suggest_tags_fallback_text():
    """Test AI service with plain text response (fallback regex)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={"response": "Here are tags: rust, performance, memory-safety"},
            )
        )

        tags = await suggest_tags("Title", "Content")
        assert "rust" in tags
        assert "performance" in tags
        assert "memory" in tags


@pytest.mark.asyncio
async def test_suggest_tags_http_error():
    """Test AI service with HTTP error."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(return_value=Response(500))

        tags = await suggest_tags("Title", "Content")
        # Fallback regex should extract words from title and content
        assert "title" in tags
        assert "content" in tags


@pytest.mark.asyncio
async def test_suggest_tags_connection_error():
    """Test AI service with connection failure."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        import httpx

        respx_mock.post("/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused", request=None)
        )

        tags = await suggest_tags("Title", "Content")
        # Fallback regex should extract words
        assert "title" in tags
        assert "content" in tags


@pytest.mark.asyncio
async def test_suggest_post_details_valid_json():
    """Test AI service with valid JSON response for post details."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "response": '{"title": "Suggested Title", "slug": "suggested-slug", "summary": "Suggested summary.", "tags": ["tag1"]}'
                },
            )
        )

        details = await suggest_post_details("Content")
        assert details == {
            "title": "Suggested Title",
            "slug": "suggested-slug",
            "summary": "Suggested summary.",
            "tags": ["tag1"],
        }


@pytest.mark.asyncio
async def test_suggest_post_details_fallback_regex():
    """Test AI service with malformed JSON but extractable details."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "response": 'Here is the JSON: "title": "Fallback Title", "slug": "fallback-slug", "summary": "Fallback summary.", "tags": ["f1"]'
                },
            )
        )

        details = await suggest_post_details("Content")
        assert details == {
            "title": "Fallback Title",
            "slug": "fallback-slug",
            "summary": "Fallback summary.",
            "tags": ["f1"],
        }


@pytest.mark.asyncio
async def test_suggest_post_details_error():
    """Test AI service handles errors gracefully."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(return_value=Response(500))

        details = await suggest_post_details("Content")
        assert details == {"title": "", "slug": "", "summary": "", "tags": []}


@pytest.mark.asyncio
async def test_suggest_tags_regex_fallback():
    """Test suggest_tags fallback to regex parsing when JSON is invalid."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": "Here are some tags: coding, python, tests"}
            )
        )
        tags = await suggest_tags("Title", "Content")
        assert "coding" in tags
        assert "python" in tags
        assert "tests" in tags


@pytest.mark.asyncio
async def test_suggest_tags_exception():
    """Test suggest_tags with an unexpected exception."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Unexpected")):
        tags = await suggest_tags("Title", "Content")
        # Fallback regex
        assert "title" in tags
        assert "content" in tags


@pytest.mark.asyncio
async def test_suggest_post_details_exception():
    """Test suggest_post_details with an unexpected exception."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Unexpected")):
        details = await suggest_post_details("Content")
        assert details == {"title": "", "slug": "", "summary": "", "tags": []}


@pytest.mark.asyncio
async def test_suggest_field_exception():
    """Test suggest_field with an unexpected exception."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Unexpected")):
        result = await suggest_field("Content", "title")
        assert result == {"title": ""}


@pytest.mark.asyncio
async def test_suggest_field_title_with_label():
    """Test AI service for single field (title) and ensuring label stripping."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": 'Title: "A Great Catchy Title"'}
            )
        )

        result = await suggest_field("Some content here", "title")
        # Should strip "Title: " and quotes
        assert result == {"title": "A Great Catchy Title"}


@pytest.mark.asyncio
async def test_suggest_field_slug():
    """Test AI service for single field (slug)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": "a-great-catchy-title"})
        )

        result = await suggest_field("Some content here", "slug")
        assert result == {"slug": "a-great-catchy-title"}


@pytest.mark.asyncio
async def test_suggest_field_summary():
    """Test AI service for single field (summary)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": "This is a brief summary."})
        )

        result = await suggest_field("Some content here", "summary")
        assert result == {"summary": "This is a brief summary."}


@pytest.mark.asyncio
async def test_suggest_field_invalid():
    """Test AI service with invalid field."""
    result = await suggest_field("Content", "invalid")
    assert result == {}


@pytest.mark.asyncio
async def test_suggest_tags_invalid_json_type():
    """Test suggest_tags with JSON that is neither list nor dict."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": "123"})
        )
        tags = await suggest_tags(
            "Deep Learning",
            "Convolutional neural networks are great for image recognition.",
        )
        # Keywords should be extracted from title/content
        assert "learning" in tags
        assert "networks" in tags


@pytest.mark.asyncio
async def test_suggest_post_details_invalid_json_type():
    """Test suggest_post_details with JSON that is not a dict."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": "[1, 2, 3]"})
        )
        details = await suggest_post_details("Content")
        assert details == {"title": "", "slug": "", "summary": "", "tags": []}


@pytest.mark.asyncio
async def test_suggest_post_details_tags_as_string():
    """Test AI service when tags are returned as a comma-separated string instead of list."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '{"title": "T", "tags": "tag1, tag2, tag3"}'}
            )
        )
        details = await suggest_post_details("Content")
        assert details["tags"] == ["tag1", "tag2", "tag3"]


@pytest.mark.asyncio
async def test_suggest_post_details_invalid_tag_type():
    """Test suggest_post_details when tags is an invalid type (e.g. number)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": '{"title": "T", "tags": 123}'})
        )
        details = await suggest_post_details("Content")
        assert details["tags"] == []


@pytest.mark.asyncio
async def test_suggest_post_details_non_string_value():
    """Test suggest_post_details when a field is not a string (e.g. number)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "response": '{"title": 123, "slug": "s", "summary": "sum", "tags": []}'
                },
            )
        )
        details = await suggest_post_details("Content")
        assert details["title"] == "123"


@pytest.mark.asyncio
async def test_suggest_tags_dict_no_list():
    """Test suggest_tags with JSON dict containing no lists."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '{"message": "no tags array"}'}
            )
        )
        tags = await suggest_tags("Target Title", "Target Content")
        assert "target" in tags
        assert "content" in tags


@pytest.mark.asyncio
async def test_suggest_tags_filtering():
    """Test filtering of short, hex, and duplicate tags."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '["a", "123-abc", "valid", "valid"]'}
            )
        )
        tags = await suggest_tags("Title", "Content")
        assert "valid" in tags
        assert "a" not in tags
        assert "123-abc" not in tags
        assert len([t for t in tags if t == "valid"]) == 1


@pytest.mark.asyncio
async def test_suggest_tags_fallback_duplicate_words():
    """Test regex fallback with duplicate words."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(return_value=Response(500))
        tags = await suggest_tags("Duplicate Duplicate", "words words words words")
        assert "duplicate" in tags
        assert "words" in tags
        assert len(tags) == 2


@pytest.mark.asyncio
async def test_suggest_post_details_tags_with_non_string():
    """Test suggest_post_details with non-string inside tags array."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '{"title": "t", "tags": [123, "valid"]}'}
            )
        )
        details = await suggest_post_details("Content")
        assert details["tags"] == ["valid"]


@pytest.mark.asyncio
async def test_suggest_post_details_regex_fallback_no_tags():
    """Test suggest_post_details regex fallback without tags field."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "response": 'Here is "title": "T", "slug": "S", "summary": "sum"'
                },
            )
        )
        details = await suggest_post_details("Content")
        assert details["tags"] == []


@pytest.mark.asyncio
async def test_chat_with_gemini_empty_content():
    """Test chat_with_gemini empty history content branch."""
    from app.services.ai import chat_with_gemini
    from unittest.mock import MagicMock

    with patch("app.services.ai._get_gemini_client") as mock_get:
        mock_client = MagicMock()
        mock_chat = MagicMock()
        mock_chat.send_message.return_value.text = "Response"
        mock_client.chats.create.return_value = mock_chat
        mock_get.return_value = mock_client

        history = [
            {"role": "user", "content": ""},
            {"role": "model", "content": "hello"},
        ]
        res = await chat_with_gemini("hi", history)
        assert res == "Response"


@pytest.mark.asyncio
async def test_generate_full_post_invalid_json():
    """Test generate_full_post when the JSON is completely unparseable."""
    from app.services.ai import generate_full_post

    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(200, json={"response": '{"title": "incomplete'})
        )
        details = await generate_full_post("topic")
        assert details == {}
