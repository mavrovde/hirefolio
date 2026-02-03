from typing import AsyncGenerator, List, Dict, Optional
import httpx
import json
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


async def chat_with_llm(
    messages: List[Dict[str, str]], stop_sequences: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from Ollama.
    Yields chunks of generated text.
    """
    try:
        payload = {
            "model": settings.generation_model,
            "messages": messages,
            "stream": True,
        }
        if stop_sequences:
            payload["options"] = {"stop": stop_sequences}

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            message = data.get("message", {})
                            content = message.get("content", "")
                            if content:
                                yield content

                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to decode Ollama response line: {line}"
                            )
                            continue
    except Exception as e:
        logger.error(f"Error in chat_with_llm: {e}", exc_info=True)
        # Return a generic error message to the client to avoid leaking internal details.
        yield "\n[System Error: An internal error occurred. Please try again later.]"
