import asyncio
import json
from typing import Any, AsyncGenerator, List, Optional

from pydantic import BaseModel
from app.config import settings
from app.logger import get_logger

from crewai import Agent, Task, Crew, Process
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler

logger = get_logger(__name__)


class AgentConfig(BaseModel):
    id: int
    description: str
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None


class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.current_agent_name = "Unknown"

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        if token:
            self.queue.put_nowait(
                {"content": token, "agent_name": self.current_agent_name}
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
) -> AsyncGenerator[str, None]:
    if not agents_config:
        return

    queue: asyncio.Queue = asyncio.Queue()
    agent_id_map = {}
    participants = []

    # 1. Create Participants (Stable Team)
    for cfg in agents_config:
        agent_name = cfg.name or f"Agent {cfg.id}"
        agent_id_map[agent_name] = cfg.id

        # Shared callback to stream tokens
        callback = StreamingCallbackHandler(queue)
        callback.current_agent_name = agent_name

        # We need to set the current agent name dynamically during execution
        # But since we use one callback instance, we might have race conditions if parallel.
        # Sequential execution is fine. We will update `callback.current_agent_name` inside the loop.

        llm = ChatOpenAI(
            model=settings.generation_model,
            base_url=f"{settings.ollama_url}/v1",
            api_key="NA",
            streaming=True,
            callbacks=[callback],
            temperature=0.7,
        )

        agent = Agent(
            role=cfg.role or "Participant",
            name=agent_name,
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
        api_key="NA",
        streaming=False,  # Moderator doesn't need to stream
        temperature=0.1,
    )

    moderator = Agent(
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
            loop = asyncio.get_running_loop()
            history: List[str] = []
            
            # Initial prompt context
            history.append(f"Topic: {topic}")

            while True:
                # 1. Participants Turn
                for agent, callback in participants:
                    # Update callback name for this turn
                    # (Though we set it on creation, if we ever reused callbacks, this ensures safety)
                    callback.current_agent_name = agent.role

                    # Build context string manually since we are breaking the chain
                    context_str = "\n".join(history[-5:]) # Keep last 5 messages for context window
                    
                    task_def = Task(
                        description=(
                            
                            f"Topic: {topic}\n"
                            f"Conversation History (Last 5 messages):\n{context_str}\n\n" 
                            f"Your Task: Read the history and respond naturally to the last speaker. "
                            f"Keep it concise (max 2-3 sentences)."
                        ),
                        expected_output="A natural response.",
                        agent=agent,
                        async_execution=False
                    )

                    # Create a mini-crew for this single turn
                    turn_crew = Crew(
                        agents=[agent],
                        tasks=[task_def],
                        verbose=False,
                        process=Process.sequential
                    )

                    # Run sync kickoff in thread
                    result_obj = await loop.run_in_executor(None, lambda: turn_crew.kickoff())
                    
                    # Store result (CrewAI returns an object or string depending on version, handle string)
                    result_text = str(result_obj)
                    formatted_msg = f"{agent.role}: {result_text}"
                    history.append(formatted_msg)

                    # 2. Moderator Check (After every speaker)
                    mod_task = Task(
                        description=(
                            f"Analyze this message for toxicity or if the conversation should end:\n"
                            f"'{result_text}'\n\n"
                            f"If 'Stop Chat' is needed, use the tool. Otherwise respond 'OK'."
                        ),
                        expected_output="OK or Stop",
                        agent=moderator,
                        async_execution=False
                    )
                    
                    mod_crew = Crew(
                        agents=[moderator],
                        tasks=[mod_task],
                        verbose=False,
                        process=Process.sequential
                    )

                    # Run moderator
                    await loop.run_in_executor(None, lambda: mod_crew.kickoff())
                    # If moderator throws StopChat exception, it is caught in the `except` block below.

                # Optional: Add a break condition if history gets too long to prevent infinite accidental loops
                if len(history) > 50:
                    break

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
            queue.put_nowait(None)

    worker_task = asyncio.create_task(run_dynamic_loop())

    # Stream tokens
    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            content = item["content"]
            name_label = item["agent_name"]
            agent_id = agent_id_map.get(name_label, 0)

            yield (
                json.dumps({"agent": agent_id, "content": content, "done": False})
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
