from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from app.services.chat import chat_with_llm
from app.services.multi_chat import multi_agent_conversation, AgentConfig

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
    Stream chat response from LLM.
    Open to public for now (or restrict to authenticated users if desired).
    """
    # If we want to restrict to users:
    # async def chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_user)):

    return StreamingResponse(
        chat_with_llm(request.messages), media_type="text/event-stream"
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
