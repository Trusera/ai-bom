"""CrewAI integration for Trusera."""

import logging
from typing import Any, Optional

from ..client import TruseraClient
from ..events import Event, EventType

logger = logging.getLogger(__name__)

try:
    from crewai import Agent, Task

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logger.warning("crewai not installed, TruseraCrewCallback unavailable")


if CREWAI_AVAILABLE:

    class TruseraCrewCallback:
        """
        CrewAI callback that sends events to Trusera.

        Captures task execution, agent actions, and tool usage.

        Example:
            >>> from crewai import Crew, Agent, Task
            >>> client = TruseraClient(api_key="tsk_...")
            >>> client.register_agent("my-crew", "crewai")
            >>> callback = TruseraCrewCallback(client)
            >>> crew = Crew(
            ...     agents=[agent],
            ...     tasks=[task],
            ...     step_callback=callback.step_callback
            ... )
            >>> crew.kickoff()
        """

        def __init__(self, client: TruseraClient) -> None:
            """
            Initialize the callback.

            Args:
                client: TruseraClient instance
            """
            self.client = client

        def step_callback(self, step_output: Any) -> None:
            """
            Callback for each step in the crew execution.

            Args:
                step_output: Output from the step
            """
            try:
                # Extract information from step output
                if hasattr(step_output, "task"):
                    self._track_task(step_output)
                elif hasattr(step_output, "action"):
                    self._track_action(step_output)
                else:
                    # Generic step tracking
                    event = Event(
                        type=EventType.DECISION,
                        name="crew_step",
                        payload={"output": str(step_output)},
                    )
                    self.client.track(event)
            except Exception as e:
                logger.error(f"Error in TruseraCrewCallback: {e}")

        def _track_task(self, step_output: Any) -> None:
            """Track task execution."""
            task = step_output.task if hasattr(step_output, "task") else None
            agent = step_output.agent if hasattr(step_output, "agent") else None

            task_name = "unknown_task"
            task_desc = ""

            if task and isinstance(task, Task):
                task_name = task.description[:50] if task.description else "unknown_task"
                task_desc = task.description or ""

            agent_role = "unknown_agent"
            if agent and isinstance(agent, Agent):
                agent_role = agent.role or "unknown_agent"

            event = Event(
                type=EventType.DECISION,
                name=f"task_{task_name}",
                payload={
                    "task_description": task_desc,
                    "output": str(step_output.output) if hasattr(step_output, "output") else "",
                },
                metadata={
                    "agent_role": agent_role,
                    "task_type": "crew_task",
                },
            )

            self.client.track(event)

        def _track_action(self, step_output: Any) -> None:
            """Track agent action."""
            action = step_output.action if hasattr(step_output, "action") else None

            action_name = "unknown_action"
            action_input = {}

            if action:
                action_name = getattr(action, "tool", "unknown_action")
                action_input = getattr(action, "tool_input", {})

            event = Event(
                type=EventType.TOOL_CALL,
                name=action_name,
                payload={
                    "input": action_input,
                    "output": str(step_output.output) if hasattr(step_output, "output") else "",
                },
                metadata={
                    "action_type": "crew_action",
                },
            )

            self.client.track(event)

        def task_callback(self, task_output: Any) -> None:
            """
            Optional callback for task completion.

            Args:
                task_output: Output from the completed task
            """
            try:
                task_desc = "unknown_task"
                if hasattr(task_output, "task") and isinstance(task_output.task, Task):
                    task_desc = task_output.task.description[:50] or "unknown_task"

                event = Event(
                    type=EventType.DECISION,
                    name=f"task_complete_{task_desc}",
                    payload={
                        "output": (
                            str(task_output.output) if hasattr(task_output, "output") else ""
                        ),
                    },
                    metadata={
                        "task_status": "completed",
                    },
                )

                self.client.track(event)
            except Exception as e:
                logger.error(f"Error in task_callback: {e}")

else:

    class TruseraCrewCallback:  # type: ignore[no-redef]
        """Placeholder when crewai is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "crewai is required for TruseraCrewCallback. "
                "Install with: pip install trusera-sdk[crewai]"
            )
