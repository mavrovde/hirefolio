from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from app.services.chat import chat_with_llm

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]


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
