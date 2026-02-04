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

            # Improve System Prompt to prevent leakage
            system_prompt = (
                f"You are {agent_name}. Role: {a_config.role}. Goal: {a_config.goal}\n"
                f"Backstory: {a_config.description}\n"
                f"Discussion Topic: {topic}\n"
                "CRITICAL INSTRUCTION: Respond directly as your character. Do NOT output your role, instructions, or introduction. Just speak."
            )

            # Construct messages properly
            llm_messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt}
            ]

            # Add conversation history
            # Only include the actual content, not the "Name: Content" format for the assistant's own turns if possible,
            # but since we are switching roles, it's safer to use 'user' role for others and 'assistant' for self if we had self-history.
            # However, here we just show the transcript.

            transcript = ""
            for msg in conversation_history[-10:]:  # Increase context slightly
                transcript += f"{msg['name']}: {msg['content']}\n"

            if transcript:
                llm_messages.append(
                    {
                        "role": "user",
                        "content": f"Current conversation so far:\n{transcript}\n\nIt is now your turn, {agent_name}. Respond concisley.",
                    }
                )
            else:
                llm_messages.append(
                    {
                        "role": "user",
                        "content": f"Start the conversation about: {topic}",
                    }
                )

            response_content = ""
            # Stop sequences to prevent generating other agents' turns
            stop_sq = ["\nAgent", "\n["]

            prefix_stripped = False
            buffer = ""

            async for chunk in chat_with_llm(llm_messages, stop_sequences=stop_sq):
                if not prefix_stripped:
                    buffer += chunk
                    # Check if buffer contains a prefix we want to strip
                    # But we only strip if we have enough chars to be sure, or if we see a separator
                    if len(buffer) > 50 or ":" in buffer:
                        trimmed = buffer.lstrip()
                        # Clean up common self-identifying prefixes
                        prefixes_to_clean = [
                            f"{agent_name}:",
                            f"[{agent_name}]:",
                            f"Agent {a_config.id}:",
                            "Introduction:",  # Specific fix for the reported issue
                            "Introduction:",
                            "1. Introduction:",
                            "Role:",
                            "Goal:",
                            "Backstory:",
                            "Discussion Topic:",
                        ]

                        # Iteratively strip prefixes until none match (to handle multiple headers)
                        while True:
                            val_len_before = len(trimmed)
                            for p in prefixes_to_clean:
                                if trimmed.lower().startswith(p.lower()):
                                    trimmed = trimmed[len(p) :].lstrip()
                                    # Also strip up to next newline if it was a header field like "Role: wife"
                                    # Heuristic: if we stripped a header title, likely the rest of the line is garbage configuration
                                    if p in [
                                        "Role:",
                                        "Goal:",
                                        "Backstory:",
                                        "Discussion Topic:",
                                    ]:
                                        if "\n" in trimmed:
                                            trimmed = trimmed.split("\n", 1)[1].lstrip()
                                        else:
                                            # If no newline yet, we might be in the middle of a line.
                                            # Wait for more data? Or just assume it's part of the header?
                                            # For this verification step, let's assume we want to strip it.
                                            pass

                            if len(trimmed) == val_len_before:
                                break

                        response_content = trimmed
                        yield (
                            json.dumps(
                                {
                                    "agent": a_config.id,
                                    "content": response_content,
                                    "done": False,
                                }
                            )
                            + "\n"
                        )
                        prefix_stripped = True
                        buffer = ""  # Clear buffer as we've emitted
                    continue

                response_content += chunk
                yield (
                    json.dumps({"agent": a_config.id, "content": chunk, "done": False})
                    + "\n"
                )

            # Fallback for very short responses
            if not prefix_stripped and buffer:
                trimmed = buffer.lstrip()
                prefixes_to_clean = [
                    f"{agent_name}:",
                    f"[{agent_name}]:",
                    f"Agent {a_config.id}:",
                    "Introduction:",
                    "1. Introduction:",
                    "Role:",
                    "Goal:",
                    "Backstory:",
                    "Discussion Topic:",
                ]
                while True:
                    val_len_before = len(trimmed)
                    for p in prefixes_to_clean:
                        if trimmed.lower().startswith(p.lower()):
                            trimmed = trimmed[len(p) :].lstrip()
                            if p in [
                                "Role:",
                                "Goal:",
                                "Backstory:",
                                "Discussion Topic:",
                            ]:
                                if "\n" in trimmed:
                                    trimmed = trimmed.split("\n", 1)[1].lstrip()
                    if len(trimmed) == val_len_before:
                        break

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
