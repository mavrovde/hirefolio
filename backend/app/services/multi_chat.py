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

    # 3. Task Generation (Upfront)
    # We generate the entire script of tasks (10 rounds * N agents) upfront.
    # The 'Dynamic' content comes from the `context` parameter, which passes
    # the output of previous tasks to the current one at runtime.
    tasks: List[Task] = []
    # Keep track of ALL speaker tasks to build cumulative context (so agents remember the whole chat)
    speaker_tasks_so_far: List[Task] = []

    MAX_ROUNDS = 10

    for round_i in range(MAX_ROUNDS):
        for agent, callback in participants:
            # Note: In a Single Crew run, we can't easily change the callback's state
            # *between* tasks because the Crew takes over control.
            # However, since we created a UNIQUE callback for each agent in the `participants` list
            # (see step 1 above), we can just set the name here once.
            callback.current_agent_name = agent.name

            # Task 1: Speak
            # We rely on CrewAI's `context` feature.
            # `context=speaker_tasks_so_far` means: "Read the outputs of all these previous tasks before running."
            t_speak = Task(
                description=(
                    f"Topic: {topic}\n"
                    f"Current Round: {round_i + 1} of {MAX_ROUNDS}\n"
                    f"Your Task:\n"
                    f"1. REVIEW the conversation so far (provided as Context).\n"
                    f"2. RESPOND naturally to the last speaker.\n"
                    f"IMPORTANT: Keep it SHORT (max 3 sentences). NO headers."
                ),
                expected_output="A natural, concise response.",
                agent=agent,
                # Context includes all previous speakers to give full history
                context=list(speaker_tasks_so_far),
                async_execution=False,
            )
            tasks.append(t_speak)
            speaker_tasks_so_far.append(t_speak)

            # Task 2: Moderate
            # The moderator acts as a checker after every single turn.
            t_mod = Task(
                description=(
                    "Analyze the previous task output for safety. "
                    "If it contains hate speech, toxicity, violations, OR if the conversation has reached a natural conclusion, use the 'Stop Chat' tool. "
                    "Otherwise, reply 'OK'."
                ),
                expected_output="OK",
                agent=moderator,
                context=[t_speak],  # Strict check of just the latest message
                async_execution=False,
            )
            tasks.append(t_mod)

    # 4. Single Crew Execution
    # One Crew, One Kickoff.
    # The 'Observer' is the callback handlers attached to the agents.
    crew = Crew(
        agents=[p[0] for p in participants] + [moderator],
        tasks=tasks,
        verbose=False,
        process=Process.sequential,
    )

    async def run_crew():
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: crew.kickoff())
        except Exception as e:
            # Check for moderator stop
            error_str = str(e)
            if "STOPPED_BY_MODERATOR" in error_str:
                clean_reason = error_str.split("STOPPED_BY_MODERATOR:")[-1].strip()
                sys_msg = f"\n[System] Conversation Terminated: {clean_reason}"
                queue.put_nowait({"content": sys_msg, "agent_name": "System"})
            else:
                logger.error(f"Crew execution failed: {e}", exc_info=True)
                queue.put_nowait({"content": f"\n[Error: {e}]", "agent_name": "System"})
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
