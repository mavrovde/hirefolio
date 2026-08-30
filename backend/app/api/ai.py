from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.logger import get_logger
from app.models.user import User
from app.services.auth import get_current_admin_user
from app.services.chat import chat_with_llm
from app.services.multi_chat import AgentConfig, multi_agent_conversation

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]


class NameRequest(BaseModel):
    description: str


class MultiChatRequest(BaseModel):
    agents: list[AgentConfig]
    topic: str
    # Bounded so a caller can ask for a short conversation (an unmocked contract
    # test wants one turn, not twenty sequential local-LLM generations — #187),
    # while the upper bound keeps the existing failsafe: an unbounded value would
    # let a single request pin the model for an arbitrarily long time.
    max_turns: int = Field(default=20, ge=1, le=20)


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Stream chat response from LLM (Ollama).
    """
    return StreamingResponse(
        chat_with_llm(request.messages), media_type="text/event-stream"
    )


@router.post("/gemini-chat")
async def gemini_chat_endpoint(
    request: ChatRequest, current_user: User = Depends(get_current_admin_user)
):
    """
    Chat with Gemini (non-streaming for now as per service implementation).
    """
    # Extract history and last message
    history = request.messages[:-1]
    last_message = request.messages[-1]["content"] if request.messages else ""

    from fastapi import HTTPException

    from app.services.ai import chat_with_gemini

    try:
        response = await chat_with_gemini(
            last_message, history, current_user.gemini_api_key
        )
        return {"response": response}
    except Exception:
        logger.exception("Gemini API Error occurred.")
        raise HTTPException(
            status_code=500, detail="Error communicating with AI service"
        )


async def _generate_agent_name(description: str) -> str:
    """Generate a creative human name for an agent based on description."""
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a creative naming assistant. Generate a single human name (First Last) that fits the persona description. Return ONLY the name, no other text.",
            },
            {
                "role": "user",
                "content": f"Description: {description}",
            },
        ]

        name = ""
        async for chunk in chat_with_llm(messages):
            name += chunk

        return name.strip().strip('"').strip("'")
    except Exception:
        # Rule 1: the fallback is correct behaviour, the SILENCE was not — a real
        # failure (model down, timeout, malformed reply) used to be
        # indistinguishable from a legitimate default (#191).
        logger.exception(
            "Agent-name generation failed; falling back to the default name"
        )
        return "Agent"


@router.post("/generate-name")
async def generate_name_endpoint(request: NameRequest):
    """
    Generate a creative human name for an agent based on description using LLM.
    Returns: { "name": "Generated Name" }
    """
    name = await _generate_agent_name(request.description)
    return {"name": name}


@router.post("/multi-chat")
async def multi_chat_endpoint(request: MultiChatRequest):
    """
    Stream multi-agent conversation with 5-minute time limit.
    N AI agents with distinct personas discuss a topic.
    """
    return StreamingResponse(
        multi_agent_conversation(request.agents, request.topic, request.max_turns),
        media_type="text/event-stream",
    )
