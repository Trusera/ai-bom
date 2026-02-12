"""AutoGen integration for Trusera."""

import logging
from typing import Any, Callable, Optional

from ..client import TruseraClient
from ..events import Event, EventType

logger = logging.getLogger(__name__)

try:
    import autogen

    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    logger.warning("pyautogen not installed, TruseraAutoGenHook unavailable")


if AUTOGEN_AVAILABLE:

    class TruseraAutoGenHook:
        """
        AutoGen message hook that sends events to Trusera.

        Captures agent messages, tool calls, and function executions.

        Example:
            >>> import autogen
            >>> client = TruseraClient(api_key="tsk_...")
            >>> client.register_agent("my-autogen", "autogen")
            >>> hook = TruseraAutoGenHook(client)
            >>> assistant = autogen.AssistantAgent(
            ...     name="assistant",
            ...     llm_config={"model": "gpt-4"},
            ... )
            >>> assistant.register_hook("process_message_before_send", hook.message_hook)
        """

        def __init__(self, client: TruseraClient) -> None:
            """
            Initialize the hook.

            Args:
                client: TruseraClient instance
            """
            self.client = client

        def message_hook(self, sender: Any, recipient: Any, message: dict[str, Any]) -> None:
            """
            Hook for AutoGen message processing.

            Args:
                sender: The agent sending the message
                recipient: The agent receiving the message
                message: The message content
            """
            try:
                sender_name = getattr(sender, "name", "unknown")
                recipient_name = getattr(recipient, "name", "unknown")

                # Extract message content
                content = message.get("content", "")

                # Check for tool/function calls
                function_call = message.get("function_call")
                if function_call:
                    self._track_function_call(sender_name, recipient_name, function_call)
                    return

                # Track regular message
                event = Event(
                    type=EventType.DECISION,
                    name=f"message_{sender_name}_to_{recipient_name}",
                    payload={
                        "content": content,
                        "sender": sender_name,
                        "recipient": recipient_name,
                    },
                    metadata={
                        "message_type": "autogen_message",
                    },
                )

                self.client.track(event)

            except Exception as e:
                logger.error(f"Error in TruseraAutoGenHook: {e}")

        def _track_function_call(
            self, sender: str, recipient: str, function_call: dict[str, Any]
        ) -> None:
            """Track a function call."""
            function_name = function_call.get("name", "unknown_function")
            arguments = function_call.get("arguments", {})

            event = Event(
                type=EventType.TOOL_CALL,
                name=function_name,
                payload={
                    "arguments": arguments,
                    "sender": sender,
                    "recipient": recipient,
                },
                metadata={
                    "call_type": "autogen_function_call",
                },
            )

            self.client.track(event)

        def function_hook(self, func: Callable[..., Any]) -> Callable[..., Any]:
            """
            Decorator to track function executions.

            Args:
                func: The function to wrap

            Returns:
                Wrapped function that tracks execution
            """

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = func(*args, **kwargs)

                    event = Event(
                        type=EventType.TOOL_CALL,
                        name=func.__name__,
                        payload={
                            "arguments": {"args": args, "kwargs": kwargs},
                            "result": str(result),
                        },
                        metadata={
                            "function_type": "autogen_function",
                        },
                    )

                    self.client.track(event)

                    return result

                except Exception as e:
                    event = Event(
                        type=EventType.TOOL_CALL,
                        name=func.__name__,
                        payload={
                            "arguments": {"args": args, "kwargs": kwargs},
                            "error": {
                                "type": type(e).__name__,
                                "message": str(e),
                            },
                        },
                        metadata={
                            "function_type": "autogen_function",
                            "success": False,
                        },
                    )

                    self.client.track(event)
                    raise

            return wrapper

        def setup_agent(self, agent: Any) -> None:
            """
            Setup hooks for an AutoGen agent.

            Args:
                agent: The AutoGen agent to instrument
            """
            if hasattr(agent, "register_hook"):
                agent.register_hook("process_message_before_send", self.message_hook)
                logger.info(f"Registered Trusera hook for agent: {getattr(agent, 'name', 'unknown')}")
            else:
                logger.warning(f"Agent {getattr(agent, 'name', 'unknown')} does not support hooks")

else:

    class TruseraAutoGenHook:  # type: ignore[no-redef]
        """Placeholder when pyautogen is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "pyautogen is required for TruseraAutoGenHook. "
                "Install with: pip install trusera-sdk[autogen]"
            )
