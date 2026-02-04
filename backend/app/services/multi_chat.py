"""Multi-agent conversation orchestration service using CrewAI."""

import asyncio
import json
from typing import Any, AsyncGenerator, List, Optional

from pydantic import BaseModel
from app.config import settings
from app.logger import get_logger

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = get_logger(__name__)


class AgentConfig(BaseModel):
    id: int
    description: str
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None


class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming LLM output to an asyncio queue."""

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.current_agent_name = "Unknown"

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        if token:
            self.queue.put_nowait(
                {"content": token, "agent_name": self.current_agent_name}
            )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        # Signal end of turn? We might rely on the main loop.
        pass


async def multi_agent_conversation(
    agents_config: List[AgentConfig],
    topic: str,
) -> AsyncGenerator[str, None]:
    """
    Orchestrate a conversation between N AI agents using CrewAI.
    """
    if not agents_config:
        return

    queue: asyncio.Queue = asyncio.Queue()

    # Map for agent IDs
    agent_id_map = {}

    # 1. Create Agents
    crew_agents = []

    for cfg in agents_config:
        agent_name = cfg.name or f"Agent {cfg.id}"
        agent_id_map[agent_name] = cfg.id

        # Create unique LLM instance per agent with a unique callback instance
        agent_queue_callback = StreamingCallbackHandler(queue)
        agent_queue_callback.current_agent_name = agent_name

        agent_llm = ChatOpenAI(
            model=settings.generation_model,
            base_url=f"{settings.ollama_url}/v1",
            api_key="NA",
            streaming=True,
            callbacks=[agent_queue_callback],
            temperature=0.7,
        )

        # Create CrewAI Agent
        agent = Agent(
            role=cfg.role or "Participant",
            name=agent_name,
            goal=cfg.goal or "Participate in the discussion.",
            backstory=cfg.description or f"You are {agent_name}.",
            llm=agent_llm,
            verbose=True,
            allow_delegation=False,
        )

        crew_agents.append(agent)

    # 2. Define Tasks (Unrolled for Sequential Debate)
    # The user wanted "equal agents" and "max_rounds".
    # In CrewAI Sequential process, we must explicitly define the sequence of tasks.
    # To simulate a debate where they listen and answer, we create a task for each agent in each turn.

    tasks = []
    MAX_ROUNDS = 3

    for round_i in range(MAX_ROUNDS):
        for agent in crew_agents:
            # Task: Listen and Respond
            # We combine "hear" and "answer" into one comprehensive task for the agent to permit flow.
            task = Task(
                description=f"Round {round_i + 1}: {topic}. Consider previous arguments. State your view clearly. Do NOT use tools. Just speak.",
                expected_output="A concise response contributing to the debate.",
                agent=agent,
                async_execution=False,
            )
            tasks.append(task)

    # 3. Create Crew
    crew = Crew(
        agents=crew_agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    # 4. Kickoff in Thread
    worker_task = None

    async def run_crew():
        try:
            # kickoff() is sync/blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: crew.kickoff())
        except Exception as e:
            logger.error(f"Crew kickoff failed: {e}", exc_info=True)
            queue.put_nowait({"content": f"[Error: {e}]", "agent_name": "System"})
        finally:
            # Signal end
            queue.put_nowait(None)

    worker_task = asyncio.create_task(run_crew())

    # 5. Stream from Queue
    try:
        while True:
            # Wait for next token
            item = await queue.get()

            if item is None:
                # Sentinel
                break

            content = item["content"]  # type: ignore
            name_label = item["agent_name"]  # type: ignore

            # Map back to ID
            agent_id = agent_id_map.get(name_label, 0)

            yield (
                json.dumps({"agent": agent_id, "content": content, "done": False})
                + "\n"
            )

            queue.task_done()
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield (
            json.dumps({"agent": 0, "content": f"[Error: {str(e)}]", "done": True})
            + "\n"
        )
    finally:
        # Check normal finish
        yield (
            json.dumps({"agent": 0, "content": "[Debate Concluded]", "done": True})
            + "\n"
        )
        if worker_task and not worker_task.done():
            worker_task.cancel()
