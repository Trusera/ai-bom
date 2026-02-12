"""Tests for TruseraClient."""

import pytest
import time
from unittest.mock import Mock, call

from trusera_sdk import TruseraClient, Event, EventType


def test_client_initialization(mock_httpx_client):
    """Test TruseraClient initialization."""
    client = TruseraClient(
        api_key="tsk_test_key",
        base_url="https://api.test.trusera.dev",
    )

    assert client.api_key == "tsk_test_key"
    assert client.base_url == "https://api.test.trusera.dev"
    assert client.flush_interval == 5.0
    assert client.batch_size == 100

    client.close()


def test_client_api_key_warning(mock_httpx_client, caplog):
    """Test warning for API key without tsk_ prefix."""
    client = TruseraClient(api_key="invalid_key")

    assert "should start with 'tsk_'" in caplog.text

    client.close()


def test_set_agent_id(trusera_client):
    """Test setting agent ID."""
    trusera_client.set_agent_id("agent_new_456")
    assert trusera_client._agent_id == "agent_new_456"


def test_register_agent(mock_httpx_client):
    """Test agent registration."""
    client = TruseraClient(api_key="tsk_test_key")

    agent_id = client.register_agent(
        name="test-agent",
        framework="langchain",
        metadata={"version": "1.0"},
    )

    assert agent_id == "agent_123"
    assert client._agent_id == "agent_123"

    # Verify API call
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    assert "/api/v1/agents" in call_args[0][0]
    assert call_args[1]["json"]["name"] == "test-agent"
    assert call_args[1]["json"]["framework"] == "langchain"

    client.close()


def test_track_event(trusera_client):
    """Test tracking an event."""
    event = Event(
        type=EventType.TOOL_CALL,
        name="test_tool",
        payload={"input": "test"},
    )

    trusera_client.track(event)

    assert trusera_client._queue.qsize() == 1


def test_track_multiple_events(trusera_client):
    """Test tracking multiple events."""
    for i in range(3):
        event = Event(
            type=EventType.TOOL_CALL,
            name=f"tool_{i}",
        )
        trusera_client.track(event)

    assert trusera_client._queue.qsize() == 3


def test_flush_events(trusera_client, mock_httpx_client):
    """Test flushing events to API."""
    # Track some events
    for i in range(3):
        event = Event(
            type=EventType.TOOL_CALL,
            name=f"tool_{i}",
        )
        trusera_client.track(event)

    # Flush
    trusera_client.flush()

    # Verify API call
    assert mock_httpx_client.post.call_count >= 1

    # Find the call that posted events
    events_posted = False
    for call_obj in mock_httpx_client.post.call_args_list:
        if "/events" in call_obj[0][0]:
            events_posted = True
            payload = call_obj[1]["json"]
            assert "events" in payload
            assert len(payload["events"]) == 3
            break

    assert events_posted, "Events were not posted to API"
    assert trusera_client._queue.qsize() == 0


def test_flush_respects_batch_size(trusera_client, mock_httpx_client):
    """Test that flush respects batch_size."""
    # Track more events than batch_size
    for i in range(10):
        event = Event(
            type=EventType.TOOL_CALL,
            name=f"tool_{i}",
        )
        trusera_client.track(event)

    # Flush (batch_size is 5)
    trusera_client.flush()

    # Should have sent 5 events, 5 remaining
    assert trusera_client._queue.qsize() == 5


def test_auto_flush_on_batch_size(trusera_client, mock_httpx_client):
    """Test automatic flush when batch_size is reached."""
    # Track events up to batch_size (5)
    for i in range(5):
        event = Event(
            type=EventType.TOOL_CALL,
            name=f"tool_{i}",
        )
        trusera_client.track(event)

    # Should trigger automatic flush
    time.sleep(0.1)  # Give it time to flush

    # Queue might not be empty immediately due to threading
    # but flush should have been called
    assert mock_httpx_client.post.call_count >= 1


def test_flush_without_agent_id(mock_httpx_client, caplog):
    """Test flush without setting agent ID."""
    client = TruseraClient(api_key="tsk_test_key")

    event = Event(type=EventType.TOOL_CALL, name="test")
    client.track(event)

    client.flush()

    assert "No agent ID set" in caplog.text

    client.close()


def test_client_context_manager(mock_httpx_client):
    """Test using client as context manager."""
    with TruseraClient(api_key="tsk_test_key") as client:
        client.set_agent_id("agent_test")
        event = Event(type=EventType.TOOL_CALL, name="test")
        client.track(event)

    # Client should be closed after exiting context
    assert client._shutdown.is_set()


def test_client_close(trusera_client, mock_httpx_client):
    """Test client close method."""
    # Track an event
    event = Event(type=EventType.TOOL_CALL, name="test")
    trusera_client.track(event)

    # Close
    trusera_client.close()

    # Should be shut down
    assert trusera_client._shutdown.is_set()

    # HTTP client should be closed
    mock_httpx_client.close.assert_called()


def test_client_close_idempotent(trusera_client):
    """Test that close can be called multiple times safely."""
    trusera_client.close()
    trusera_client.close()  # Should not raise


def test_track_after_shutdown(trusera_client, caplog):
    """Test tracking after client is shut down."""
    trusera_client.close()

    event = Event(type=EventType.TOOL_CALL, name="test")
    trusera_client.track(event)

    assert "shutting down" in caplog.text.lower()
