from typing import Optional, List
import httpx
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


async def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding vector for text using Ollama."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/embeddings",
                json={
                    "model": settings.embedding_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding")
    except (httpx.HTTPError, httpx.ConnectError) as e:
        logger.error(f"Error generating embedding: {e}", exc_info=True)
        return None
