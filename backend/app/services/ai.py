import json
import re

import httpx

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

try:
    from google import genai
    from google.genai import errors as genai_errors

    HAS_GEMINI = True
    logger.debug("google.genai imported successfully.")
except ImportError as e:  # pragma: no cover
    HAS_GEMINI = False
    logger.debug("google.genai import failed: %s", e)


def _get_gemini_client(user_api_key: str | None = None):
    """Configures and returns a Gemini client instance."""
    api_key = user_api_key or settings.gemini_api_key

    logger.debug("_get_gemini_client called. Has key? %s", bool(api_key))

    if not HAS_GEMINI:
        logger.debug("HAS_GEMINI is False; Gemini unavailable.")
        return None

    if not api_key:
        logger.debug("No Gemini API key provided.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        logger.debug("Gemini client created successfully.")
        return client
    except Exception as e:
        logger.error(f"Failed to configure Gemini client: {e}")
        return None


def _is_model_unavailable_error(exc: Exception) -> bool:
    """True only for a "model not found / unavailable" (HTTP 404) API error.

    Such a 404 is returned *before* any inference runs, so retrying a
    different model does not double-bill. Every other error (rate limit,
    quota, server error, bad request) returns False so we do NOT make a second
    billable Gemini call and instead let the caller fall back to the free
    local Ollama path.
    """
    if not HAS_GEMINI:  # pragma: no cover - no client can exist without the SDK
        return False
    if isinstance(exc, genai_errors.APIError):
        status = str(getattr(exc, "status", "") or "").upper()
        return getattr(exc, "code", None) == 404 or status == "NOT_FOUND"
    return False


async def _generate_text_gemini(
    prompt: str, user_api_key: str | None = None
) -> str | None:
    """Helper to generate text using Gemini, returning None if failed or not configured."""
    client = _get_gemini_client(user_api_key)
    if not client:
        return None

    # The new SDK `google-genai` uses the synchronous
    # `client.models.generate_content`.
    model = settings.gemini_model
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text
    except Exception as exc:
        # Only retry with the fallback model when the primary model itself is
        # unavailable (HTTP 404) — that error is raised before any billing, so
        # the retry is at most one paid call. Any other error must NOT trigger
        # a second billable request: return None so the caller falls back to
        # the free local Ollama path.
        if not _is_model_unavailable_error(exc):
            logger.error(f"Gemini generation error: {exc}")
            return None

        fallback = settings.gemini_model_fallback
        if not fallback or fallback == model:
            logger.error(f"Gemini model '{model}' unavailable: {exc}")
            return None

        logger.warning(
            f"Gemini model '{model}' unavailable; retrying with '{fallback}'"
        )
        try:
            response = client.models.generate_content(model=fallback, contents=prompt)
            return response.text
        except Exception as exc2:
            logger.error(f"Gemini generation error: {exc2}")
            return None


async def suggest_tags(
    title: str, content: str, user_api_key: str | None = None
) -> list[str]:
    """
    Generate tag suggestions using Gemini (primary) or Ollama (fallback).
    Returns a list of strings (max 5).
    """
    prompt = f"""
    You are a technical blog tagging assistant.
    Analyze the following blog post and extract exactly 5 relevant tags.
    Focus on specific technologies, concepts, frameworks, or key themes discussed in the text.
    Avoid generic terms like "guide", "introduction", or "tutorial".
    Return ONLY a JSON array of strings (e.g., ["tag1", "tag2"]).
    
    Title: {title}
    Content: {content[:10000]}
    """

    # Try Gemini first
    gemini_response = await _generate_text_gemini(prompt)
    if gemini_response:
        response_text = gemini_response
        logger.info(
            f"Using Gemini for suggest_tags. Raw response: {response_text[:200]}..."
        )
    else:
        logger.info("Using Ollama for suggest_tags (fallback)")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": settings.fast_generation_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "")
        except Exception:
            logger.exception("Unexpected error in suggest_tags (Ollama)")
            response_text = ""

    # Process response_text (same logic for both)
    tags = []
    try:
        # Clean markdown code blocks if present (Gemini loves ```json ... ```)
        cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text).strip()
        parsed_json = json.loads(cleaned_text)

        if isinstance(parsed_json, list):
            tags = parsed_json
        elif isinstance(parsed_json, dict):
            for v in parsed_json.values():
                if isinstance(v, list):
                    tags = v
                    break
    except json.JSONDecodeError:
        tags = re.findall(r"\b\w+\b", response_text)

    # Process and filter tags
    processed_tags = []
    stop_words = {
        "here",
        "are",
        "some",
        "tags",
        "the",
        "is",
        "for",
        "and",
        "title",
        "slug",
        "summary",
    }
    for t in tags:
        t_str = str(t).lower().strip().replace(" ", "-")
        if t_str in stop_words:
            continue
        if (
            len(t_str) > 2
            and not re.match(r"^[0-9a-f\-]+$", t_str)
            and t_str not in processed_tags
        ):
            processed_tags.append(t_str)

    # Fallback extraction from content if LLM failed completely
    if not processed_tags:
        source_text = f"{title} {content[:500]}".lower()
        words = re.findall(r"\b[a-z]{5,}\b", source_text)
        for w in words:
            if w not in processed_tags:
                processed_tags.append(w)
                if len(processed_tags) >= 5:
                    break

    return processed_tags[:5]


async def suggest_post_details(
    content: str, user_api_key: str | None = None
) -> dict[str, str | list[str]]:
    """
    Generate title, slug, summary, and tags suggestions using Gemini (primary) or Ollama (fallback).
    """
    prompt = f"""
    You are a technical blog editor assistant.
    Based on the following blog content, suggest a catchy title, a URL-friendly slug, a brief 1-2 sentence summary, and 5 relevant tags.
    Focus on specific technologies and key themes for the tags.
    
    Rules:
    1. Return ONLY a valid JSON object.
    2. Keys must be "title", "slug", "summary", and "tags".
    3. "tags" must be a list of strings.
    4. Do NBOT use placeholders like "[Snipped]" or "Insert text here". Generate actual content based on the input.
    5. Do not include any explanation or markdown formatting.
    
    Content: {content[:10000]}
    """

    gemini_response = await _generate_text_gemini(prompt)
    if gemini_response:
        response_text = gemini_response
        logger.info(
            f"Using Gemini for suggest_post_details. Raw response: {response_text[:200]}..."
        )
    else:
        logger.info("Using Ollama for suggest_post_details (fallback)")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": settings.fast_generation_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "")
        except Exception:
            logger.exception("Unexpected error in suggest_post_details")
            return {"title": "", "slug": "", "summary": "", "tags": []}

    try:
        cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text).strip()
        details = json.loads(cleaned_text)

        if isinstance(details, dict):
            clean_details: dict[str, str | list[str]] = {}
            for k, v in details.items():
                if k == "tags":
                    if isinstance(v, list):
                        clean_tags = []
                        for t in v:
                            if isinstance(t, str):
                                clean_tags.append(t.strip().strip('"').strip("'"))
                        clean_details[k] = clean_tags[:5]
                    elif isinstance(v, str):
                        clean_details[k] = [
                            t.strip() for t in v.split(",") if t.strip()
                        ][:5]
                    else:
                        clean_details[k] = []
                elif isinstance(v, str):
                    v = re.sub(
                        r"^(title|slug|summary|suggestion|description):\s*",
                        "",
                        v,
                        flags=re.IGNORECASE,
                    )
                    clean_details[k] = v.strip().strip('"').strip("'")
                else:
                    clean_details[k] = v
            return {
                "title": str(clean_details.get("title", "")),
                "slug": str(clean_details.get("slug", "")),
                "summary": str(clean_details.get("summary", "")),
                "tags": list(clean_details.get("tags", [])),
            }
    except json.JSONDecodeError:
        # Basic extraction as fallback
        title_match = re.search(r'"title":\s*"([^"]+)"', response_text)
        slug_match = re.search(r'"slug":\s*"([^"]+)"', response_text)
        summary_match = re.search(r'"summary":\s*"([^"]+)"', response_text)
        tags_match = re.search(r'"tags":\s*\[([^\]]+)\]', response_text)

        tags = []
        if tags_match:
            tags = [t.strip().strip('"') for t in tags_match.group(1).split(",")][:5]

        return {
            "title": title_match.group(1) if title_match else "Suggested Title",
            "slug": slug_match.group(1) if slug_match else "suggested-slug",
            "summary": summary_match.group(1)
            if summary_match
            else "Suggested summary...",
            "tags": tags,
        }

    return {"title": "", "slug": "", "summary": "", "tags": []}


async def suggest_field(
    content: str, field: str, user_api_key: str | None = None
) -> dict[str, str]:
    """
    Generate a suggestion for a single field using Gemini (primary) or Ollama (fallback).
    """
    prompts = {
        "title": f"Suggest a catchy, professional, and SEO-friendly title for the following blog content. Return ONLY the raw title text. DO NOT prefix it with 'Title:', 'Suggestion:', or any other label. DO NOT use quotes.\n\nContent: {content[:10000]}",
        "slug": f"Suggest a URL-friendly slug (kebab-case) for the following blog content. Return ONLY the raw slug text. DO NOT prefix it with 'Slug:', 'URL:', or any other label. DO NOT use quotes.\n\nContent: {content[:10000]}",
        "summary": f"Summarize the following blog content in exactly 1-2 concise, engaging sentences for a social media preview. Return ONLY the raw summary text. DO NOT prefix it with 'Summary:', 'Description:', or any other label. DO NOT use quotes.\n\nContent: {content[:10000]}",
    }

    if field not in prompts:
        return {}

    prompt = prompts[field]
    response_text = ""

    gemini_response = await _generate_text_gemini(prompt)
    if gemini_response:
        response_text = gemini_response
        logger.info(f"Using Gemini for suggest_field({field})")
    else:
        logger.info(f"Using Ollama for suggest_field({field}) (fallback)")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": settings.fast_generation_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "")
        except Exception:
            logger.exception(f"Error suggesting {field}")
            return {field: ""}

    suggestion = response_text.strip()
    suggestion = re.sub(
        r"^(title|slug|summary|suggestion|description):\s*",
        "",
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = suggestion.strip().strip('"').strip("'")
    return {field: suggestion}


async def chat_with_gemini(
    message: str, history: list[dict] | None = None, user_api_key: str | None = None
) -> str:
    """
    Chat with Gemini model, maintaining conversation history.
    """
    client = _get_gemini_client(user_api_key)
    if not client:
        return "Gemini is not configured."

    history = history or []
    try:
        # Convert simple history format to Gemini format
        # Input: [{"role": "user", "content": "msg"}, {"role": "assistant", "content": "msg"}]
        # Output: [{"role": "user", "parts": ["msg"]}, {"role": "model", "parts": ["msg"]}]
        gemini_history = []
        for msg in history:
            role = "user" if msg.get("role") in ["user", "system"] else "model"
            content = msg.get("content", "")
            if content:
                gemini_history.append({"role": role, "parts": [{"text": content}]})

        # Use the configured (cheap flash-tier) model for chat.
        model = settings.gemini_model
        chat = client.chats.create(model=model, history=gemini_history)

        response = chat.send_message(message)
        return response.text
    except Exception as exc:
        # Only retry with the fallback model when the primary model is
        # unavailable (HTTP 404); any other error must not fire a second
        # billable call.
        if not _is_model_unavailable_error(exc):
            logger.exception("Error in chat_with_gemini")
            return "Error communicating with AI service."

        fallback = settings.gemini_model_fallback
        if not fallback or fallback == settings.gemini_model:
            logger.exception("Error in chat_with_gemini")
            return "Error communicating with AI service."

        try:
            chat = client.chats.create(model=fallback, history=gemini_history)
            response = chat.send_message(message)
            return response.text
        except Exception:
            logger.exception("Error in chat_with_gemini")
            return "Error communicating with AI service."


async def generate_full_post(
    topic: str,
    keywords: list[str] | None = None,
    language: str = "en",
    user_api_key: str | None = None,
) -> dict[str, str | list[str]]:
    """
    Generate a complete blog post including title, slug, summary, tags, and markdown content.
    Returns a dictionary with these fields.
    """
    keywords_str = ", ".join(keywords) if keywords else "general tech topics"

    prompt = f"""
    You are a professional technical blog writer.
    Write a comprehensive, engaging, and SEO-optimized blog post about: "{topic}".
    
    Language: {language}
    Keywords to include: {keywords_str}
    
    Structure:
    1. Title: Catchy and relevant.
    2. Slug: URL-friendly version of the title.
    3. Summary: 1-2 sentence overview.
    4. Tags: 3-5 relevant tags.
    5. Content: The full blog post body in Markdown format. Use H2 (##) and H3 (###) for structure. Include an introduction, several body sections, and a conclusion. 
    
    Output Format:
    Return ONLY a valid JSON object with the following keys:
    - "title": (string)
    - "slug": (string)
    - "summary": (string)
    - "tags": (list of strings)
    - "content": (string, markdown)
    
    Do not include any other text or markdown formatting (like ```json ... ```) outside the JSON object.
    """

    # Try Gemini first
    gemini_response = await _generate_text_gemini(prompt)
    response_text = ""

    if gemini_response:
        response_text = gemini_response
        logger.info("Using Gemini for generate_full_post")
    else:
        logger.info("Using Ollama for generate_full_post (fallback)")
        # Note: Local LLMs might struggle with large outputs or JSON strictness for full posts
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": settings.fast_generation_model,  # Might need a larger model for full posts
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "")
        except Exception:
            logger.exception("Unexpected error in generate_full_post")
            return {}

    # Parse JSON
    try:
        # Robust extraction: find first { and last }
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned_text = response_text[start_idx : end_idx + 1]
            post_data = json.loads(cleaned_text)
        else:
            # Fallback to regex if braces not found (unlikely for valid JSON)
            cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text).strip()
            post_data = json.loads(cleaned_text)

        # Validate structure
        required_keys = ["title", "slug", "summary", "tags", "content"]
        if all(k in post_data for k in required_keys):
            # basic cleaning
            post_data["tags"] = [
                str(t).strip() for t in post_data["tags"] if isinstance(t, str)
            ][:5]
            return post_data
        else:
            logger.warning(f"Generated post details missing keys: {post_data.keys()}")
            return {}

    except json.JSONDecodeError:
        logger.error(
            f"Failed to decode JSON from generate_full_post response: {response_text[:100]}..."
        )
        return {}
    except Exception:
        logger.exception("Error processing generated post")
        return {}
