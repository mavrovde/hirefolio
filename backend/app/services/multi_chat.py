"""Multi-agent conversation orchestration service.

Manages conversations between N AI agents with distinct personas.
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel
from app.services.chat import chat_with_llm
from app.logger import get_logger

logger = get_logger(__name__)

MAX_CONVERSATION_DURATION = 300  # 5 minutes
MAX_TURNS = 15  # Increased turns for multi-agent


class AgentConfig(BaseModel):
    id: int
    description: str
    name: Optional[str] = None


async def multi_agent_conversation(
    agents: List[AgentConfig],
    topic: str,
) -> AsyncGenerator[str, None]:
    """
    Orchestrate a conversation between N AI agents.

    Args:
        agents: List of agent configurations (id, description, name)
        topic: The conversation topic

    Yields:
        JSON strings with format: {"agent": id, "content": "...", "done": false}
    """
    start_time = time.time()
    # History stores metadata: {'agent_id': int, 'agent_name': str, 'content': str}
    conversation_history: list[Dict] = []

    if not agents:
        return

    try:
        current_agent_idx = 0

        for turn in range(MAX_TURNS):
            # Check time limit
            elapsed = time.time() - start_time
            if elapsed >= MAX_CONVERSATION_DURATION:
                yield (
                    json.dumps(
                        {
                            "agent": 0,
                            "content": "[Conversation time limit reached]",
                            "done": True,
                        }
                    )
                    + "\n"
                )
                break

            current_agent = agents[current_agent_idx]
            agent_name = current_agent.name or f"Agent {current_agent.id}"

            # 1. Build System Prompt
            other_agents_names = [
                a.name or f"Agent {a.id}" for a in agents if a.id != current_agent.id
            ]
            others_str = ", ".join(other_agents_names)

            system_prompt = (
                f"You are {agent_name}. Your persona: {current_agent.description}\n"
                f"You are in a group discussion with {others_str} about: {topic}\n"
                "Respond naturally from your perspective. Keep responses concise (2-3 sentences).\n"
                "Be engaging and stay in character. React to what others have said."
            )

            # 2. Build Message History for LLM
            llm_messages = [{"role": "system", "content": system_prompt}]

            # Add context (last 6 messages to keep context window manageable)
            context_size = min(6, len(conversation_history))
            recent_history = conversation_history[-context_size:]

            for msg in recent_history:
                if msg["agent_id"] == current_agent.id:
                    # My own previous messages
                    llm_messages.append(
                        {"role": "assistant", "content": msg["content"]}
                    )
                else:
                    # Others' messages -> User role, prefixed with name
                    llm_messages.append(
                        {
                            "role": "user",
                            "content": f"[{msg['agent_name']}]: {msg['content']}",
                        }
                    )

            # 3. Add prompt trigger if it's the very first turn of the conversation
            if turn == 0 and current_agent_idx == 0:
                llm_messages.append(
                    {"role": "user", "content": f"Start a discussion about: {topic}"}
                )
            elif not recent_history:
                # Should not happen typically unless context is empty
                pass

            # 4. Stream Response
            response_content = ""
            async for chunk in chat_with_llm(llm_messages):
                response_content += chunk
                yield (
                    json.dumps(
                        {"agent": current_agent.id, "content": chunk, "done": False}
                    )
                    + "\n"
                )

            # 5. Update History
            conversation_history.append(
                {
                    "agent_id": current_agent.id,
                    "agent_name": agent_name,
                    "content": response_content,
                }
            )

            # Signal end of turn
            yield (
                json.dumps(
                    {
                        "agent": current_agent.id,
                        "content": "",
                        "done": False,
                        "turn_complete": True,
                    }
                )
                + "\n"
            )

            # 6. Next Agent (Round Robin)
            current_agent_idx = (current_agent_idx + 1) % len(agents)

            # Small delay
            await asyncio.sleep(0.5)

        # Conversation completed natural loop end
        yield (
            json.dumps(
                {"agent": 0, "content": "[Conversation completed]", "done": True}
            )
            + "\n"
        )

    except Exception as e:
        logger.error(f"Error in multi_agent_conversation: {e}", exc_info=True)
        yield (
            json.dumps({"agent": 0, "content": f"[Error: {str(e)}]", "done": True})
            + "\n"
        )
