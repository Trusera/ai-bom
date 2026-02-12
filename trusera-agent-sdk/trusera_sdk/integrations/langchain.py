"""LangChain integration for Trusera."""

import logging
from typing import Any, Optional
from uuid import UUID

from ..client import TruseraClient
from ..events import Event, EventType

logger = logging.getLogger(__name__)

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("langchain-core not installed, TruseraCallbackHandler unavailable")


if LANGCHAIN_AVAILABLE:

    class TruseraCallbackHandler(BaseCallbackHandler):
        """
        LangChain callback handler that sends events to Trusera.

        Captures LLM invocations, tool calls, and chain executions.

        Example:
            >>> from langchain.llms import OpenAI
            >>> client = TruseraClient(api_key="tsk_...")
            >>> client.register_agent("my-agent", "langchain")
            >>> handler = TruseraCallbackHandler(client)
            >>> llm = OpenAI(callbacks=[handler])
            >>> llm("What is AI?")
        """

        def __init__(self, client: TruseraClient) -> None:
            """
            Initialize the callback handler.

            Args:
                client: TruseraClient instance
            """
            super().__init__()
            self.client = client
            self._run_metadata: dict[str, dict[str, Any]] = {}

        def on_llm_start(
            self,
            serialized: dict[str, Any],
            prompts: list[str],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[list[str]] = None,
            metadata: Optional[dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            """Handle LLM start event."""
            self._run_metadata[str(run_id)] = {
                "prompts": prompts,
                "serialized": serialized,
                "tags": tags or [],
                "metadata": metadata or {},
            }

        def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> None:
            """Handle LLM end event."""
            run_id_str = str(run_id)
            start_data = self._run_metadata.pop(run_id_str, {})

            model_name = (
                start_data.get("serialized", {}).get("name")
                or start_data.get("serialized", {}).get("_type")
                or "unknown"
            )

            # Extract generated text
            generations = []
            for generation_list in response.generations:
                for gen in generation_list:
                    generations.append(gen.text if hasattr(gen, "text") else str(gen))

            event = Event(
                type=EventType.LLM_INVOKE,
                name=f"llm_{model_name}",
                payload={
                    "prompts": start_data.get("prompts", []),
                    "generations": generations,
                    "model": model_name,
                },
                metadata={
                    "run_id": run_id_str,
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "tags": start_data.get("tags", []),
                    "llm_output": response.llm_output or {},
                },
            )

            self.client.track(event)

        def on_tool_start(
            self,
            serialized: dict[str, Any],
            input_str: str,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[list[str]] = None,
            metadata: Optional[dict[str, Any]] = None,
            inputs: Optional[dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            """Handle tool start event."""
            self._run_metadata[str(run_id)] = {
                "input_str": input_str,
                "inputs": inputs or {},
                "serialized": serialized,
                "tags": tags or [],
                "metadata": metadata or {},
            }

        def on_tool_end(
            self,
            output: str,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> None:
            """Handle tool end event."""
            run_id_str = str(run_id)
            start_data = self._run_metadata.pop(run_id_str, {})

            tool_name = start_data.get("serialized", {}).get("name", "unknown_tool")

            event = Event(
                type=EventType.TOOL_CALL,
                name=tool_name,
                payload={
                    "input": start_data.get("input_str", ""),
                    "inputs": start_data.get("inputs", {}),
                    "output": output,
                },
                metadata={
                    "run_id": run_id_str,
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "tags": start_data.get("tags", []),
                },
            )

            self.client.track(event)

        def on_tool_error(
            self,
            error: BaseException,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> None:
            """Handle tool error event."""
            run_id_str = str(run_id)
            start_data = self._run_metadata.pop(run_id_str, {})

            tool_name = start_data.get("serialized", {}).get("name", "unknown_tool")

            event = Event(
                type=EventType.TOOL_CALL,
                name=tool_name,
                payload={
                    "input": start_data.get("input_str", ""),
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                },
                metadata={
                    "run_id": run_id_str,
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "success": False,
                },
            )

            self.client.track(event)

        def on_chain_start(
            self,
            serialized: dict[str, Any],
            inputs: dict[str, Any],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[list[str]] = None,
            metadata: Optional[dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            """Handle chain start event."""
            self._run_metadata[str(run_id)] = {
                "inputs": inputs,
                "serialized": serialized,
                "tags": tags or [],
                "metadata": metadata or {},
            }

        def on_chain_end(
            self,
            outputs: dict[str, Any],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> None:
            """Handle chain end event."""
            run_id_str = str(run_id)
            start_data = self._run_metadata.pop(run_id_str, {})

            chain_name = (
                start_data.get("serialized", {}).get("name")
                or start_data.get("serialized", {}).get("_type")
                or "unknown_chain"
            )

            event = Event(
                type=EventType.DECISION,
                name=f"chain_{chain_name}",
                payload={
                    "inputs": start_data.get("inputs", {}),
                    "outputs": outputs,
                },
                metadata={
                    "run_id": run_id_str,
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "tags": start_data.get("tags", []),
                },
            )

            self.client.track(event)

else:

    class TruseraCallbackHandler:  # type: ignore[no-redef]
        """Placeholder when langchain-core is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "langchain-core is required for TruseraCallbackHandler. "
                "Install with: pip install trusera-sdk[langchain]"
            )
