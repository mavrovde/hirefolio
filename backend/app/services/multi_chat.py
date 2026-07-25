import asyncio
import json
import warnings
import httpx
import re
from typing import Any, AsyncGenerator, List, Optional
from pydantic import BaseModel, SecretStr
from crewai import Agent
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from app.config import settings
from app.logger import get_logger

# Suppress Pydantic V1/V2 mixing warnings from CrewAI internals
warnings.filterwarnings("ignore", message="Mixing V1 models and V2 models")

logger = get_logger(__name__)


class AgentConfig(BaseModel):
    id: int
    description: str
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None


class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        self.current_agent_name = "Unknown"

    def on_llm_new_token(self, token: Any, **kwargs: Any) -> None:
        if token:
            # Safely put tokens from a background thread into the main loop's queue
            self.loop.call_soon_threadsafe(
                self.queue.put_nowait,
                {"content": token, "agent_name": self.current_agent_name},
            )


class ChatMessage(BaseModel):
    agent_name: str
    content: str

    def to_string(self) -> str:
        return f"{self.agent_name}: {self.content}"


class StopChatTool(BaseTool):
    name: str = "Stop Chat"
    description: str = (
        "Stops the conversation immediately. Input should be the reason for stopping."
    )

    def _run(self, reason: str) -> str:
        # We raise an exception to immediately halt execution
        raise Exception(f"STOPPED_BY_MODERATOR: {reason}")


async def multi_agent_conversation(
    agents_config: List[AgentConfig],
    topic: str,
    max_turns: int = 20,  # Failsafe turn limit
) -> AsyncGenerator[str, None]:
    if not agents_config:
        return

    queue: asyncio.Queue = asyncio.Queue()
    agent_id_map = {}
    participants = []

    loop_main = asyncio.get_running_loop()

    # 1. Create Participants (Stable Team)
    for cfg in agents_config:
        agent_role = cfg.role or "Participant"
        agent_id_map[agent_role] = cfg.id

        # Shared callback to stream tokens
        callback = StreamingCallbackHandler(queue, loop_main)
        callback.current_agent_name = agent_role

        # We need to set the current agent name dynamically during execution
        # But since we use one callback instance, we might have race conditions if parallel.
        # Sequential execution is fine. We will update `callback.current_agent_name` inside the loop.

        llm = ChatOpenAI(
            model=settings.generation_model,
            base_url=f"{settings.ollama_url}/v1",
            api_key=SecretStr("NA"),
            streaming=True,
            callbacks=[callback],
            temperature=0.7,
        )

        agent = Agent(
            role=agent_role,
            goal=cfg.goal or "Participate deeply in the discussion.",
            backstory=cfg.description,
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        participants.append((agent, callback))

    # 2. Create Moderator (Stable)
    stop_tool = StopChatTool()
    moderator_llm = ChatOpenAI(
        model=settings.generation_model,
        base_url=f"{settings.ollama_url}/v1",
        api_key=SecretStr("NA"),
        streaming=False,  # Moderator doesn't need to stream
        temperature=0.1,
    )

    Agent(
        role="Moderator",
        name="Invisible Moderator",
        goal="Ensure the conversation remains safe, on-topic, and appropriate.",
        backstory="You are an invisible AI safety system. You monitor conversations for toxicity.",
        llm=moderator_llm,
        verbose=False,
        allow_delegation=False,
        tools=[stop_tool],
    )

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
                        "content": f"\n[Infrastructure Error: Cannot connect to Ollama at {settings.ollama_url}]",
                        "agent_name": "System",
                    }
                )
                return

            history: List[str] = []

            # Initial prompt context
            history.append(f"Topic: {topic}")
            turns = 0
            while turns < max_turns:
                turns += 1
                # 1. Participants Turn
                for agent, callback in participants:
                    # Use role since CrewAI Agent doesn't have a 'name' field in this version
                    callback.current_agent_name = agent.role
                    context_str = "\n".join(history[-3:])
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
                    for p_agent, _ in participants:
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
                    except Exception as e:
                        if "STOPPED_BY_MODERATOR" in str(e):
                            raise e
                        full_text = f"[Error: {e}]"

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

                    # No moderator for this high-performance test run

                # The debate continues until stopped by the user or the moderator tool.
                # History is managed by keeping the last 8 messages for context.
                if len(history) > 20:
                    history = history[-10:]

        except Exception as e:
            # Check for moderator stop
            error_str = str(e)
            if "STOPPED_BY_MODERATOR" in error_str:
                # Extract reason
                clean_reason = error_str.split("STOPPED_BY_MODERATOR:")[-1].strip()
                # Remove quotes if present
                clean_reason = clean_reason.strip("'").strip('"')
                sys_msg = f"\n[System] Conversation Terminated: {clean_reason}"
                queue.put_nowait({"content": sys_msg, "agent_name": "System"})
            else:
                logger.error(f"Crew execution failed: {e}", exc_info=True)
                queue.put_nowait({"content": f"\n[Error: {e}]", "agent_name": "System"})
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

            yield (
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

            queue.task_done()

    finally:
        yield (
            json.dumps({"agent": 0, "content": "[Conversation Finished]", "done": True})
            + "\n"
        )

        if worker_task and not worker_task.done():
            worker_task.cancel()
