"""Edge-case branch coverage for app/services/ai.py."""
import json
import pytest
from unittest.mock import patch, AsyncMock
from app.services import ai
from app.config import settings


# ---- suggest_tags branches -------------------------------------------------
@pytest.mark.asyncio
async def test_suggest_tags_dict_no_list_values():
    """Branch 114->122 / 115->114: parsed dict whose values are not lists.

    No list value -> tags stays empty -> triggers content fallback extraction.
    """
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value='{"a": "notalist", "b": 5}'),
    ):
        tags = await ai.suggest_tags("PythonTitle", "programming language content")
    # Fell through to fallback extraction from title/content
    assert isinstance(tags, list)
    assert len(tags) > 0


@pytest.mark.asyncio
async def test_suggest_tags_filters_short_hex_and_duplicates():
    """Branches 130->126, 131->126: too-short/hex tag skipped; duplicate skipped."""
    # "ab" too short (len<=2); "deadbeef" is hex-only -> filtered.
    # "python" duplicated -> second occurrence skipped by 131->126.
    payload = json.dumps(["ab", "deadbeef", "python", "python", "django"])
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=payload),
    ):
        tags = await ai.suggest_tags("Title", "Content")
    assert "ab" not in tags
    assert "deadbeef" not in tags
    assert tags.count("python") == 1
    assert "django" in tags


@pytest.mark.asyncio
async def test_suggest_tags_content_fallback_dedup():
    """Branches 138->144 / 139->138: fallback extraction dedups repeated words."""
    # Return empty JSON list -> processed_tags empty -> content fallback runs.
    # Content repeats "hello" (>=5 chars) so 139->138 dedup path is exercised.
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value="[]"),
    ):
        tags = await ai.suggest_tags(
            "Title", "hello hello world friend planet garden hello"
        )
    assert tags.count("hello") == 1
    assert len(tags) <= 5


# ---- suggest_post_details branches ----------------------------------------
@pytest.mark.asyncio
async def test_suggest_post_details_tags_non_str_item():
    """Branch 201->200: tags list containing a non-str item is skipped."""
    payload = json.dumps(
        {"title": "T", "slug": "s", "summary": "sum", "tags": ["good", 123, None]}
    )
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=payload),
    ):
        details = await ai.suggest_post_details("Content")
    assert details["tags"] == ["good"]


@pytest.mark.asyncio
async def test_suggest_post_details_jsondecode_no_tags():
    """Branch 227->230: JSONDecodeError fallback with no 'tags' match -> empty tags."""
    # Not valid JSON, and contains title/slug/summary but no tags array.
    text = 'garbage "title": "My T" and "slug": "my-s" and "summary": "sm" no tags'
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=text),
    ):
        details = await ai.suggest_post_details("Content")
    assert details["title"] == "My T"
    assert details["tags"] == []


# ---- chat_with_gemini branch ----------------------------------------------
@pytest.mark.asyncio
async def test_chat_with_gemini_empty_history_content():
    """Branch 302->299: history item with empty content is skipped."""
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "answer"
    mock_chat.send_message.return_value = mock_resp
    mock_client.models.start_chat.return_value = mock_chat

    history = [
        {"role": "user", "content": ""},  # empty -> skipped (302->299)
        {"role": "assistant", "content": "prev"},
    ]
    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("q", history)
    assert res == "answer"
    _, kwargs = mock_client.models.start_chat.call_args
    # Only the non-empty history entry converted
    assert kwargs["history"] == [{"role": "model", "parts": ["prev"]}]


# ---- generate_full_post branches ------------------------------------------
@pytest.mark.asyncio
async def test_generate_full_post_success_all_keys():
    """Lines 402-406: valid JSON with all required keys returns cleaned data."""
    payload = json.dumps(
        {
            "title": "T",
            "slug": "s",
            "summary": "sum",
            "tags": ["x", 1, "y"],
            "content": "body",
        }
    )
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=payload),
    ):
        res = await ai.generate_full_post("Topic")
    assert res["title"] == "T"
    assert res["tags"] == ["x", "y"]  # non-str filtered


@pytest.mark.asyncio
async def test_generate_full_post_no_braces_regex_fallback():
    """Lines 398-399: no braces -> regex fallback json.loads, then raises JSONDecodeError -> {}."""
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value="no json here at all"),
    ):
        res = await ai.generate_full_post("Topic")
    assert res == {}


@pytest.mark.asyncio
async def test_generate_full_post_missing_keys():
    """Lines 408-409: valid JSON missing required keys -> {}."""
    payload = json.dumps({"title": "T"})
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=payload),
    ):
        res = await ai.generate_full_post("Topic")
    assert res == {}


@pytest.mark.asyncio
async def test_generate_full_post_tags_non_iterable_generic_except():
    """Lines 414-416: tags is a non-iterable (int) -> generic except -> {}."""
    # all keys present but tags is an int -> list comprehension over int raises TypeError
    payload = json.dumps(
        {"title": "T", "slug": "s", "summary": "sm", "tags": 5, "content": "c"}
    )
    with patch(
        "app.services.ai._generate_text_gemini",
        new=AsyncMock(return_value=payload),
    ):
        res = await ai.generate_full_post("Topic")
    assert res == {}


@pytest.mark.asyncio
async def test_generate_full_post_ollama_success():
    """Lines 380-382: Gemini None -> Ollama httpx path success."""
    import respx
    from httpx import Response

    payload = {
        "title": "OT",
        "slug": "ot",
        "summary": "os",
        "tags": ["t"],
        "content": "oc",
    }
    with patch("app.services.ai._generate_text_gemini", new=AsyncMock(return_value=None)):
        with respx.mock(base_url=settings.ollama_url) as respx_mock:
            respx_mock.post("/api/generate").mock(
                return_value=Response(200, json={"response": json.dumps(payload)})
            )
            res = await ai.generate_full_post("Topic")
    assert res["title"] == "OT"
