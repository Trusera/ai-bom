"""Decorators for automatic event tracking."""

import asyncio
import functools
import inspect
import logging
import time
from typing import Any, Callable, Optional, TypeVar, cast

from .client import TruseraClient
from .events import Event, EventType

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Global default client
_default_client: Optional[TruseraClient] = None


def set_default_client(client: TruseraClient) -> None:
    """Set the default client for the @monitor decorator."""
    global _default_client
    _default_client = client


def get_default_client() -> Optional[TruseraClient]:
    """Get the default client."""
    return _default_client


def monitor(
    event_type: EventType = EventType.TOOL_CALL,
    name: Optional[str] = None,
    client: Optional[TruseraClient] = None,
    capture_args: bool = True,
    capture_result: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to automatically track function calls as Trusera events.

    Works with both sync and async functions. Captures function name,
    arguments, return value, and execution duration.

    Args:
        event_type: Type of event to create
        name: Custom name for the event (defaults to function name)
        client: TruseraClient instance (uses default if not provided)
        capture_args: Whether to include function arguments in the event
        capture_result: Whether to include the return value in the event

    Example:
        >>> @monitor(event_type=EventType.TOOL_CALL)
        ... def search(query: str) -> list[str]:
        ...     return ["result1", "result2"]
    """

    def decorator(func: F) -> F:
        event_name = name or func.__name__

        # Handle async functions
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _client = client or get_default_client()
                if not _client:
                    logger.warning(
                        f"No Trusera client configured for {func.__name__}, skipping tracking"
                    )
                    return await func(*args, **kwargs)

                start_time = time.time()
                error: Optional[Exception] = None
                result = None

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = e
                    raise
                finally:
                    duration = time.time() - start_time
                    _create_and_track_event(
                        _client,
                        event_type,
                        event_name,
                        func,
                        args,
                        kwargs,
                        result,
                        error,
                        duration,
                        capture_args,
                        capture_result,
                    )

            return cast(F, async_wrapper)

        # Handle sync functions
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _client = client or get_default_client()
                if not _client:
                    logger.warning(
                        f"No Trusera client configured for {func.__name__}, skipping tracking"
                    )
                    return func(*args, **kwargs)

                start_time = time.time()
                error: Optional[Exception] = None
                result = None

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = e
                    raise
                finally:
                    duration = time.time() - start_time
                    _create_and_track_event(
                        _client,
                        event_type,
                        event_name,
                        func,
                        args,
                        kwargs,
                        result,
                        error,
                        duration,
                        capture_args,
                        capture_result,
                    )

            return cast(F, sync_wrapper)

    return decorator


def _create_and_track_event(
    client: TruseraClient,
    event_type: EventType,
    event_name: str,
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
    error: Optional[Exception],
    duration: float,
    capture_args: bool,
    capture_result: bool,
) -> None:
    """Create and track an event from function execution."""
    payload: dict[str, Any] = {}

    # Capture arguments
    if capture_args:
        try:
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            payload["arguments"] = _serialize_args(bound_args.arguments)
        except Exception as e:
            logger.debug(f"Failed to capture arguments: {e}")
            payload["arguments"] = {"error": str(e)}

    # Capture result
    if capture_result and result is not None:
        payload["result"] = _serialize_value(result)

    # Capture error
    if error:
        payload["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    # Metadata
    metadata = {
        "function": func.__name__,
        "module": func.__module__,
        "duration_ms": round(duration * 1000, 2),
        "success": error is None,
    }

    event = Event(
        type=event_type,
        name=event_name,
        payload=payload,
        metadata=metadata,
    )

    client.track(event)


def _serialize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Serialize function arguments for JSON."""
    return {k: _serialize_value(v) for k, v in args.items()}


def _serialize_value(value: Any) -> Any:
    """
    Serialize a value for JSON.

    Handles common types and falls back to string representation.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    elif isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    else:
        # Fall back to string representation for complex types
        return str(value)
