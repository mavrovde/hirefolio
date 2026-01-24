import httpx
import json
import re
from app.config import settings

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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.generation_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json" # Force JSON mode if model supports it (Ollama does)
                },
            )
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "")
            
            # Parse JSON
            try:
                tags = json.loads(response_text)
                if isinstance(tags, list):
                    return [str(t).lower().replace(" ", "-") for t in tags[:5]]
                # Try to find list in dict if wrapped
                if isinstance(tags, dict):
                    for k, v in tags.items():
                        if isinstance(v, list):
                            return [str(t).lower().replace(" ", "-") for t in v[:5]]
            except json.JSONDecodeError:
                # Fallback: simple text parsing if JSON mode fails or model hallucinates
                # Look for comma separated or newline separated words
                words = re.findall(r'\b\w+\b', response_text)
                # Filter out common stop words if necessary, but for now just take top unique long words
                unique_tags = []
                for w in words:
                    w = w.lower()
                    if len(w) > 3 and w not in unique_tags:
                        unique_tags.append(w)
                        if len(unique_tags) >= 5:
                            break
                return unique_tags
                
            return []
            
    except (httpx.HTTPError, httpx.ConnectError) as e:
        print(f"Error generating tags: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in suggest_tags: {e}")
        return []
