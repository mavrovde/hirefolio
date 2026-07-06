"""A single generic AgentExecutor that powers every role, parameterized by its
RoleSpec. Each role's behaviour is its system prompt + skills from the roster.
"""
from __future__ import annotations

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart, TaskState
from a2a.utils import new_task

from .brain import think
from .roster import RoleSpec


class RoleExecutor(AgentExecutor):
    def __init__(self, spec: RoleSpec):
        self.spec = spec

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input() or ""

        # Ensure there is a task to attach status/artifacts to.
        task = context.current_task
        if task is None:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            result = await think(self.spec.system_prompt, query, role_title=self.spec.title)
            await updater.add_artifact(
                [Part(root=TextPart(text=result))],
                name=f"{self.spec.key}-result",
            )
            await updater.complete()
        except Exception as exc:  # surface failures as a proper A2A failed state
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message(
                    [Part(root=TextPart(text=f"{self.spec.key} error: {exc}"))]
                ),
                final=True,
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is not None:
            updater = TaskUpdater(event_queue, task.id, task.context_id)
            await updater.update_status(TaskState.canceled, final=True)
