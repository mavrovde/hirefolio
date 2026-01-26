from typing import Union, List
import re
import httpx
import json
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


async def suggest_tags(title: str, content: str) -> list[str]:
    """
    Generate tag suggestions using Ollama.
    Returns a list of strings (max 5).
    """
    prompt = f"""
    You are a blog tagging assistant.
    Suggest exactly 5 short, relevant tags for the following blog post.
    Return ONLY a JSON array of strings. Do not include any explanation or markdown formatting.
    
    Title: {title}
    Content: {content[:500]}...
    """

    try:
        # Increase timeout for slower CPU inference or larger contexts
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.generation_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",  # Force JSON mode if model supports it (Ollama does)
                },
            )
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "")

            # Parse JSON
            tags = []
            try:
                parsed_json = json.loads(response_text)
                if isinstance(parsed_json, list):
                    tags = parsed_json
                elif isinstance(parsed_json, dict):
                    for k, v in parsed_json.items():
                        if isinstance(v, list):
                            tags = v
                            break
            except json.JSONDecodeError:
                # Fallback: simple text parsing if JSON mode fails
                tags = re.findall(r"\b\w+\b", response_text)

            # Process and filter tags
            processed_tags = []
            # Improved stop words for conversational AI lead-ins
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
                # Filter out short tags, common numbers, or hex-heavy strings (hallucinations like UUID parts)
                if len(t_str) > 2 and not re.match(r"^[0-9a-f\-]+$", t_str):
                    if t_str not in processed_tags:
                        processed_tags.append(t_str)

            # Final Fallback: if no valid tags, extract from title/content
            if not processed_tags:
                source_text = f"{title} {content[:500]}".lower()
                # Find words > 4 chars, not including common stop words
                words = re.findall(r"\b[a-z]{5,}\b", source_text)
                for w in words:
                    if w not in processed_tags:
                        processed_tags.append(w)
                        if len(processed_tags) >= 5:
                            break

            return processed_tags[:5]
    except Exception as e:
        logger.error(f"Unexpected error in suggest_tags: {e}", exc_info=True)
        return []


async def suggest_post_details(content: str) -> dict[str, Union[str, List[str]]]:
    """
    Generate title, slug, summary, and tags suggestions using Ollama.
    Returns a dictionary with 'title', 'slug', 'summary', and 'tags'.
    """
    prompt = f"""
    You are a blog editor assistant.
    Based on the following blog content, suggest a catchy title, a URL-friendly slug, a brief 1-2 sentence summary, and 5 relevant tags.
    
    Rules:
    1. Return ONLY a valid JSON object.
    2. Keys must be "title", "slug", "summary", and "tags".
    3. "tags" must be a list of strings.
    4. Do NBOT use placeholders like "[Snipped]" or "Insert text here". Generate actual content based on the input.
    5. Do not include any explanation or markdown formatting.
    
    Content: {content[:1500]}...
    """

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.generation_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "")

            try:
                details = json.loads(response_text)
                if isinstance(details, dict):
                    # Clean all string values in the dict
                    clean_details: dict[str, Union[str, list[str]]] = {}
                    for k, v in details.items():
                        if k == "tags":
                            if isinstance(v, list):
                                # Ensure all tags are clean strings
                                clean_tags = []
                                for t in v:
                                    if isinstance(t, str):
                                        clean_tags.append(
                                            t.strip().strip('"').strip("'")
                                        )
                                clean_details[k] = clean_tags[:5]
                            elif isinstance(v, str):
                                # Handle case where model returns tags as a comma-separated string
                                clean_details[k] = [
                                    t.strip() for t in v.split(",") if t.strip()
                                ][:5]
                            else:
                                clean_details[k] = []
                        elif isinstance(v, str):
                            # Remove labels like "Title: " or "Summary: " and surrounding quotes
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
                    tags = [
                        t.strip().strip('"') for t in tags_match.group(1).split(",")
                    ][:5]

                return {
                    "title": title_match.group(1) if title_match else "Suggested Title",
                    "slug": slug_match.group(1) if slug_match else "suggested-slug",
                    "summary": summary_match.group(1)
                    if summary_match
                    else "Suggested summary...",
                    "tags": tags,
                }

            return {"title": "", "slug": "", "summary": "", "tags": []}

    except Exception as e:
        logger.error(f"Unexpected error in suggest_post_details: {e}", exc_info=True)
        return {"title": "", "slug": "", "summary": "", "tags": []}


async def suggest_field(content: str, field: str) -> dict[str, str]:
    """
    Generate a suggestion for a single field using Ollama.
    Returns a dictionary with the field as key.
    """
    prompts = {
        "title": f"Suggest a catchy, professional, and SEO-friendly title for the following blog content. Return ONLY the raw title text. DO NOT prefix it with 'Title:', 'Suggestion:', or any other label. DO NOT use quotes.\n\nContent: {content[:1000]}",
        "slug": f"Suggest a URL-friendly slug (kebab-case) for the following blog content. Return ONLY the raw slug text. DO NOT prefix it with 'Slug:', 'URL:', or any other label. DO NOT use quotes.\n\nContent: {content[:1000]}",
        "summary": f"Summarize the following blog content in exactly 1-2 concise, engaging sentences for a social media preview. Return ONLY the raw summary text. DO NOT prefix it with 'Summary:', 'Description:', or any other label. DO NOT use quotes.\n\nContent: {content[:1000]}",
    }

    if field not in prompts:
        return {}

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.generation_model,
                    "prompt": prompts[field],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            suggestion = data.get("response", "").strip()
            # Defensive cleaning: remove common labels and quotes
            suggestion = re.sub(
                r"^(title|slug|summary|suggestion|description):\s*",
                "",
                suggestion,
                flags=re.IGNORECASE,
            )
            suggestion = suggestion.strip().strip('"').strip("'")
            return {field: suggestion}
    except Exception as e:
        logger.error(f"Error suggesting {field}: {e}", exc_info=True)
        return {field: ""}
