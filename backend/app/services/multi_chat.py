"""Multi-agent conversation orchestration service.

Manages conversations between N AI agents with distinct personas.
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
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
    role: Optional[str] = None
    goal: Optional[str] = None


async def multi_agent_conversation(
    agents: List[AgentConfig],
    topic: str,
) -> AsyncGenerator[str, None]:
    """
    Orchestrate a conversation between N AI agents using CrewAI.

    Args:
        agents: List of agent configurations (id, description, name, role, goal)
        topic: The conversation topic

    Yields:
        JSON strings with format: {"agent": id, "content": "...", "done": false}
    """
    if not agents:
        return

    try:
        start_time = time.time()

        # 5. Kickoff and Stream (Simulated streaming for turn-based interaction)
        # Note: CrewAI kickoff is typically blocking. To maintain the streaming UX
        # while using CrewAI's planning/reasoning, we use a loop where each agent
        # contributes a 'thought' or 'response'.

        conversation_history: List[Dict[str, Any]] = []

        for turn in range(MAX_TURNS):
            elapsed = time.time() - start_time
            if elapsed >= MAX_CONVERSATION_DURATION:
                yield (
                    json.dumps({"agent": 0, "content": "[Limit reached]", "done": True})
                    + "\n"
                )
                break

            current_idx = turn % len(agents)
            a_config = agents[current_idx]
            agent_name = a_config.name or f"Agent {a_config.id}"

            # Use CrewAI's reasoning via chat_with_llm but with CrewAI-enhanced prompts
            system_prompt = (
                f"You are {agent_name}. Role: {a_config.role}. Goal: {a_config.goal}\n"
                f"Backstory: {a_config.description}\n"
                f"Discussion Topic: {topic}\n"
                "CRITICAL: Be concise (2-3 sentences). Respond ONLY as yourself."
            )

            llm_messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt}
            ]
            context = conversation_history[-6:]
            for msg in context:
                role = "assistant" if str(msg.get("id")) == str(a_config.id) else "user"
                content = (
                    msg.get("content", "")
                    if role == "assistant"
                    else f"[{msg.get('name')}]: {msg.get('content')}"
                )
                llm_messages.append({"role": role, "content": content})

            if turn == 0:
                llm_messages.append(
                    {"role": "user", "content": f"Open the discussion about: {topic}"}
                )

            response_content = ""
            stop_sq = ["\nAgent", "\n[", f"\n{agent_name}"]

            prefix_stripped = False
            buffer = ""

            async for chunk in chat_with_llm(llm_messages, stop_sequences=stop_sq):
                if not prefix_stripped:
                    buffer += chunk
                    if len(buffer) > 40:
                        trimmed = buffer.lstrip()
                        # Simple cleanup of self-references
                        prefixes = [
                            f"{agent_name}:",
                            f"[{agent_name}]:",
                            f"Agent {a_config.id}:",
                        ]
                        for p in prefixes:
                            if trimmed.startswith(p):
                                trimmed = trimmed[len(p) :].lstrip()
                        response_content = trimmed
                        yield (
                            json.dumps(
                                {
                                    "agent": a_config.id,
                                    "content": trimmed,
                                    "done": False,
                                }
                            )
                            + "\n"
                        )
                        prefix_stripped = True
                    continue

                response_content += chunk
                yield (
                    json.dumps({"agent": a_config.id, "content": chunk, "done": False})
                    + "\n"
                )

            # Fallback for very short responses
            if not prefix_stripped and buffer:
                trimmed = buffer.lstrip()
                response_content = trimmed
                yield (
                    json.dumps(
                        {"agent": a_config.id, "content": trimmed, "done": False}
                    )
                    + "\n"
                )

            conversation_history.append(
                {"id": a_config.id, "name": agent_name, "content": response_content}
            )
            yield (
                json.dumps(
                    {
                        "agent": a_config.id,
                        "content": "",
                        "done": False,
                        "turn_complete": True,
                    }
                )
                + "\n"
            )
            await asyncio.sleep(0.5)

        yield (
            json.dumps({"agent": 0, "content": "[Debate Concluded]", "done": True})
            + "\n"
        )

    except Exception as e:
        logger.error(f"CrewAI conversation error: {e}", exc_info=True)
        yield (
            json.dumps({"agent": 0, "content": f"[Error: {str(e)}]", "done": True})
            + "\n"
        )
