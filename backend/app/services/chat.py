from typing import AsyncGenerator, List, Dict
import httpx
import json
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


async def chat_with_llm(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from Ollama.
    Yields chunks of generated text.
    """
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.generation_model,
                    "messages": messages,
                    "stream": True,
                },
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
        yield f"\n[System Error: {str(e)}]"
