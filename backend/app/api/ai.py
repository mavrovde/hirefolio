from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from app.services.chat import chat_with_llm
from app.services.multi_chat import multi_agent_conversation, AgentConfig
from app.models.user import User
from app.services.auth import get_current_admin_user
from fastapi import Depends

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]


class NameRequest(BaseModel):
    description: str


class MultiChatRequest(BaseModel):
    agents: List[AgentConfig]
    topic: str


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

    from app.services.ai import chat_with_gemini
    from fastapi import HTTPException

    try:
        response = await chat_with_gemini(
            last_message, history, current_user.gemini_api_key
        )
        return {"response": response}
    except Exception as e:
        import logging
        logging.error(f"Gemini API Error: {str(e)}")
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
        multi_agent_conversation(request.agents, request.topic),
        media_type="text/event-stream",
    )
