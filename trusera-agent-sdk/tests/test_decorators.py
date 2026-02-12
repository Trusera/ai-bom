"""Tests for decorator functionality."""

import pytest
import asyncio
from unittest.mock import Mock

from trusera_sdk import monitor, set_default_client, EventType


def test_monitor_sync_function(trusera_client):
    """Test @monitor decorator on sync function."""
    set_default_client(trusera_client)

    @monitor()
    def test_function(x: int, y: int) -> int:
        return x + y

    result = test_function(2, 3)

    assert result == 5
    assert trusera_client._queue.qsize() == 1

    # Check event
    event = trusera_client._queue.get()
    assert event.type == EventType.TOOL_CALL
    assert event.name == "test_function"
    assert event.payload["arguments"]["x"] == 2
    assert event.payload["arguments"]["y"] == 3
    assert event.payload["result"] == 5
    assert event.metadata["success"] is True
    assert event.metadata["duration_ms"] > 0


@pytest.mark.asyncio
async def test_monitor_async_function(trusera_client):
    """Test @monitor decorator on async function."""
    set_default_client(trusera_client)

    @monitor()
    async def async_function(value: str) -> str:
        await asyncio.sleep(0.01)
        return value.upper()

    result = await async_function("hello")

    assert result == "HELLO"
    assert trusera_client._queue.qsize() == 1

    # Check event
    event = trusera_client._queue.get()
    assert event.type == EventType.TOOL_CALL
    assert event.name == "async_function"
    assert event.payload["arguments"]["value"] == "hello"
    assert event.payload["result"] == "HELLO"


def test_monitor_with_custom_name(trusera_client):
    """Test @monitor with custom event name."""
    set_default_client(trusera_client)

    @monitor(name="custom_operation")
    def test_function() -> str:
        return "done"

    test_function()

    event = trusera_client._queue.get()
    assert event.name == "custom_operation"


def test_monitor_with_event_type(trusera_client):
    """Test @monitor with custom event type."""
    set_default_client(trusera_client)

    @monitor(event_type=EventType.DATA_ACCESS)
    def query_database() -> list[str]:
        return ["result1", "result2"]

    query_database()

    event = trusera_client._queue.get()
    assert event.type == EventType.DATA_ACCESS


def test_monitor_without_capture_args(trusera_client):
    """Test @monitor with capture_args=False."""
    set_default_client(trusera_client)

    @monitor(capture_args=False)
    def test_function(secret: str) -> str:
        return secret.upper()

    test_function("password123")

    event = trusera_client._queue.get()
    assert "arguments" not in event.payload


def test_monitor_without_capture_result(trusera_client):
    """Test @monitor with capture_result=False."""
    set_default_client(trusera_client)

    @monitor(capture_result=False)
    def test_function() -> str:
        return "sensitive_data"

    test_function()

    event = trusera_client._queue.get()
    assert "result" not in event.payload


def test_monitor_with_exception(trusera_client):
    """Test @monitor capturing exceptions."""
    set_default_client(trusera_client)

    @monitor()
    def failing_function() -> None:
        raise ValueError("Something went wrong")

    with pytest.raises(ValueError):
        failing_function()

    event = trusera_client._queue.get()
    assert event.metadata["success"] is False
    assert event.payload["error"]["type"] == "ValueError"
    assert event.payload["error"]["message"] == "Something went wrong"


@pytest.mark.asyncio
async def test_monitor_async_with_exception(trusera_client):
    """Test @monitor on async function with exception."""
    set_default_client(trusera_client)

    @monitor()
    async def async_failing() -> None:
        await asyncio.sleep(0.01)
        raise RuntimeError("Async error")

    with pytest.raises(RuntimeError):
        await async_failing()

    event = trusera_client._queue.get()
    assert event.metadata["success"] is False
    assert event.payload["error"]["type"] == "RuntimeError"


def test_monitor_with_explicit_client(trusera_client):
    """Test @monitor with explicitly passed client."""
    # Don't set default client

    @monitor(client=trusera_client)
    def test_function() -> str:
        return "test"

    test_function()

    assert trusera_client._queue.qsize() == 1


def test_monitor_without_client(caplog):
    """Test @monitor without any client configured."""
    set_default_client(None)

    @monitor()
    def test_function() -> str:
        return "test"

    result = test_function()

    assert result == "test"
    assert "No Trusera client configured" in caplog.text


def test_monitor_preserves_function_metadata():
    """Test that @monitor preserves function metadata."""
    @monitor()
    def documented_function(x: int) -> int:
        """This is a docstring."""
        return x * 2

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is a docstring."


def test_monitor_with_complex_types(trusera_client):
    """Test @monitor with complex argument types."""
    set_default_client(trusera_client)

    @monitor()
    def process_data(data: dict[str, list[int]]) -> int:
        return sum(data.get("numbers", []))

    result = process_data({"numbers": [1, 2, 3]})

    assert result == 6
    event = trusera_client._queue.get()
    assert event.payload["arguments"]["data"]["numbers"] == [1, 2, 3]
