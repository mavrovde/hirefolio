import asyncio
import json
from typing import Any, AsyncGenerator, List, Optional

from pydantic import BaseModel
from app.config import settings
from app.logger import get_logger

from crewai import Agent, Task, Crew, Process
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


async def multi_agent_conversation(
    agents_config: List[AgentConfig],
    topic: str,
) -> AsyncGenerator[str, None]:
    if not agents_config:
        return

    queue: asyncio.Queue = asyncio.Queue()
    agent_id_map = {}
    crew_agents = []

    # Create agents
    for cfg in agents_config:
        agent_name = cfg.name or f"Agent {cfg.id}"
        agent_id_map[agent_name] = cfg.id

        callback = StreamingCallbackHandler(queue)
        callback.current_agent_name = agent_name

        llm = ChatOpenAI(
            model=settings.generation_model,
            base_url=f"{settings.ollama_url}/v1",
            api_key="NA",
            streaming=True,
            callbacks=[callback],
            temperature=0.5,
        )

        agent = Agent(
            role=cfg.role or "Participant",
            name=agent_name,
            goal=cfg.goal or "Participate in the discussion.",
            backstory=cfg.description,
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )

        crew_agents.append(agent)

    # Shared conversation buffer
    conversation_history = ""

    tasks = []
    MAX_ROUNDS = 3

    for round_i in range(MAX_ROUNDS):
        for agent in crew_agents:
            task = Task(
                description=(
                    f"Topic: {topic}\n"
                    f"Conversation so far:\n{conversation_history}\n\n"
                    f"Your turn. Respond naturally to the discussion. "
                    f"Do NOT restate the entire history. Just continue the dialog."
                ),
                expected_output="A natural conversational response.",
                agent=agent,
                async_execution=False,
            )
            tasks.append(task)

    # Crew
    crew = Crew(
        agents=crew_agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )

    async def run_crew():
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: crew.kickoff())

            # Append final result to history
            nonlocal conversation_history
            conversation_history += f"\n{result}"

        except Exception as e:
            logger.error(f"Crew kickoff failed: {e}", exc_info=True)
            queue.put_nowait({"content": f"[Error: {e}]", "agent_name": "System"})
        finally:
            queue.put_nowait(None)

    worker_task = asyncio.create_task(run_crew())

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
