from openai import AsyncOpenAI

from app.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


async def get_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text using OpenAI."""
    if not client:
        return None

    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
