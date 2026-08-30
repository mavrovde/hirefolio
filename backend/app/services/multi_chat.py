import asyncio
import json
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


class AgentConfig(BaseModel):
    id: int
    description: str
    name: str | None = None
    role: str | None = None
    goal: str | None = None


class ChatMessage(BaseModel):
    agent_name: str
    content: str

    def to_string(self) -> str:
        return f"{self.agent_name}: {self.content}"


@dataclass(frozen=True)
class Participant:
    """One debate participant.

    Deliberately a plain data holder: generation happens through a direct HTTP
    stream to Ollama's ``/api/chat`` below, so this path needs no agent
    framework. It used to build a crewai ``Agent`` wrapping a LangChain
    ``ChatOpenAI`` client, which crewai 1.x rejects (``Agent.llm`` accepts
    ``str | BaseLLM | dict``) — raising a ValidationError before the streaming
    generator's first yield and breaking the endpoint (issue #180).
    """

    role: str
    goal: str
    backstory: str


def _build_participants(
    agents_config: list[AgentConfig],
) -> tuple[list[Participant], dict[str, int]]:
    """Turn the request payload into participants + a role -> agent id map."""
    participants: list[Participant] = []
    agent_id_map: dict[str, int] = {}

    for cfg in agents_config:
        agent_role = cfg.role or "Participant"
        agent_id_map[agent_role] = cfg.id
        participants.append(
            Participant(
                role=agent_role,
                goal=cfg.goal or "Participate deeply in the discussion.",
                backstory=cfg.description,
            )
        )

    return participants, agent_id_map


def _stream_chunk(agent_id: int, content: str, turn_complete: bool = False) -> str:
    return (
        json.dumps(
            {
                "agent": agent_id,
                "content": content,
                "done": False,
                "turn_complete": turn_complete,
            }
        )
        + "\n"
    )


def _final_chunk() -> str:
    return (
        json.dumps({"agent": 0, "content": "[Conversation Finished]", "done": True})
        + "\n"
    )


async def multi_agent_conversation(
    agents_config: list[AgentConfig],
    topic: str,
    max_turns: int = 20,  # Failsafe turn limit
) -> AsyncGenerator[str, None]:
    if not agents_config:
        return

    queue: asyncio.Queue = asyncio.Queue()

    # 1. Create Participants (Stable Team). Any setup failure has to degrade into
    # an error *on the stream*: the response headers are already sent by the time
    # this generator runs, so raising here would close the body mid-chunk and the
    # browser would only see a connection error (issue #180).
    try:
        participants, agent_id_map = _build_participants(agents_config)
    except Exception:
        logger.exception("Failed to set up the multi-agent conversation")
        # CodeQL py/stack-trace-exposure: the reason is logged above, never
        # streamed — exception text can carry internals (paths, config, driver
        # detail) and this stream is public.
        yield _stream_chunk(0, "\n[Error: the conversation could not be started.]")
        yield _final_chunk()
        return

    async def run_dynamic_loop():
        try:
            logger.info(f"Starting dynamic loop. OLLAMA_URL: {settings.ollama_url}")

            # Pre-flight check
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama_url}/api/tags", timeout=5
                    )
                    if resp.status_code == 200:
                        logger.info("Successfully connected to Ollama.")
                    else:
                        logger.error(f"Ollama returned status {resp.status_code}")
            except Exception as conn_err:
                logger.error(f"Ollama connection check failed: {conn_err}")
                await queue.put(
                    {
                        "content": "\n[Infrastructure Error: the AI backend is unavailable.]",
                        "agent_name": "System",
                    }
                )
                return

            history: list[str] = []

            # Initial prompt context
            history.append(f"Topic: {topic}")
            turns = 0
            while turns < max_turns:
                turns += 1
                # 1. Participants Turn
                for agent in participants:
                    # COMPLETION STYLE PROMPT: Act like we are already in the middle of a script
                    context_str = "\n".join(history[-3:])

                    # ULTRA-MINIMAL PROMPT: No headers, no structure, just completion.
                    system_prompt = (
                        f"You are {agent.role} ({agent.backstory}). "
                        f"Focus: {agent.goal}. Topic: {topic}. "
                        f"Respond to the chat in 1 short unique sentence from your perspective."
                    )

                    user_content = f"History:\n{context_str}\n{agent.role}:"

                    # Dynamically build stop sequences from participants
                    stop_sequences = ["\n", "Dialogue:", "System:", "Narrator:"]
                    for p_agent in participants:
                        role_stop = f"{p_agent.role}:"
                        if role_stop not in stop_sequences:
                            stop_sequences.append(role_stop)

                    # DIRECT HTTP CALL to Ollama
                    url = f"{settings.ollama_url}/api/chat"
                    payload = {
                        "model": settings.generation_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": True,
                        "options": {
                            "num_ctx": 4096,
                            "num_predict": 60,
                            "temperature": 0.8,
                            "repeat_penalty": 1.2,
                            "stop": stop_sequences,
                        },
                    }

                    full_text = ""
                    streamed_any_content = False
                    try:
                        async with httpx.AsyncClient() as client:
                            async with client.stream(
                                "POST", url, json=payload, timeout=30
                            ) as response:
                                if response.status_code == 200:
                                    async for line in response.aiter_lines():
                                        if line:
                                            try:
                                                data = json.loads(line)
                                                chunk_text = data.get(
                                                    "message", {}
                                                ).get("content", "")
                                                if chunk_text:
                                                    full_text += chunk_text
                                                    streamed_any_content = True
                                                    queue.put_nowait(
                                                        {
                                                            "content": chunk_text,
                                                            "agent_name": agent.role,
                                                        }
                                                    )
                                                if data.get("done"):
                                                    break
                                            except json.JSONDecodeError:
                                                continue
                    except Exception:
                        logger.exception("Multi-agent turn failed for %s", agent.role)
                        full_text = "[Error: this turn could not be generated.]"

                    # AGGRESSIVE POST-PROCESS: Regex to strip ANY leading labels
                    clean_text = full_text.strip()

                    # 1. Generic strip: Remove anything before a colon at the very start of the text
                    # (e.g., "Astronaut: ", "Leo: ", "Sentence: ", "Restaurant Owner: ")
                    clean_text = re.sub(r"^[^:\n]{1,30}:\s*", "", clean_text)

                    # 2. Strip leftover artifacts
                    patterns = [
                        r"\(.*?\)",  # Remove parentheticals
                        r"\n.*$",  # Remove junk after first newline
                    ]
                    for pattern in patterns:
                        clean_text = re.sub(pattern, "", clean_text).strip()

                    # Final failsafe clean
                    clean_text = clean_text.strip('"' + "'" + "()[]{}").strip()

                    # If empty or too short, fallback to a goal-aligned statement
                    if not clean_text or len(clean_text) < 5:
                        # Use the agent's goal to generate a generic fallback if cleaning stripped everything
                        clean_text = (
                            f"I believe we must focus on my goal: {agent.goal}."
                        )

                    # Final aggressive quote stripping for the history/storage
                    # Matches starting quote, content, and ending quote if they surround the whole text
                    clean_text = re.sub(r'^["\'](.*)["\']$', r"\1", clean_text.strip())
                    clean_text = clean_text.strip('"' + "'" + "()[]{}").strip()

                    if not streamed_any_content and clean_text:
                        queue.put_nowait(
                            {"content": clean_text, "agent_name": agent.role}
                        )

                    history.append(f"{agent.role}: {clean_text}")

                    # Signal end of turn for this agent
                    queue.put_nowait(
                        {"content": "", "agent_name": agent.role, "turn_complete": True}
                    )

                # The debate continues until the client disconnects or the turn
                # limit is reached. History is trimmed to keep the context small.
                if len(history) > 20:
                    history = history[-10:]

        except Exception:
            logger.exception("Multi-agent conversation failed")
            queue.put_nowait(
                {
                    "content": "\n[Error: the conversation ended unexpectedly.]",
                    "agent_name": "System",
                }
            )
        finally:
            log_msg = "Finishing dynamic loop."
            logger.info(log_msg)
            queue.put_nowait(None)

    worker_task = asyncio.create_task(run_dynamic_loop())

    # Stream tokens
    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            content = item.get("content", "")
            name_label = item.get("agent_name", "Unknown")
            agent_id = agent_id_map.get(name_label, 0)
            turn_complete = item.get("turn_complete", False)

            yield _stream_chunk(agent_id, content, turn_complete)

            queue.task_done()

    finally:
        yield _final_chunk()

        if worker_task and not worker_task.done():
            worker_task.cancel()
