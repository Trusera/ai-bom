"""Tests for event types and structures."""

import pytest
from datetime import datetime, timezone

from trusera_sdk import Event, EventType


def test_event_type_enum():
    """Test EventType enum values."""
    assert EventType.TOOL_CALL.value == "tool_call"
    assert EventType.LLM_INVOKE.value == "llm_invoke"
    assert EventType.DATA_ACCESS.value == "data_access"
    assert EventType.API_CALL.value == "api_call"
    assert EventType.FILE_WRITE.value == "file_write"
    assert EventType.DECISION.value == "decision"


def test_event_creation():
    """Test creating an Event."""
    event = Event(
        type=EventType.TOOL_CALL,
        name="test_tool",
        payload={"input": "test"},
        metadata={"duration": 100},
    )

    assert event.type == EventType.TOOL_CALL
    assert event.name == "test_tool"
    assert event.payload == {"input": "test"}
    assert event.metadata == {"duration": 100}
    assert event.id is not None
    assert event.timestamp is not None


def test_event_defaults():
    """Test Event with default values."""
    event = Event(type=EventType.LLM_INVOKE, name="test")

    assert event.payload == {}
    assert event.metadata == {}
    assert len(event.id) > 0
    assert event.timestamp is not None


def test_event_to_dict():
    """Test Event serialization to dict."""
    event = Event(
        type=EventType.TOOL_CALL,
        name="search",
        payload={"query": "test"},
        metadata={"duration_ms": 150},
    )

    data = event.to_dict()

    assert data["type"] == "tool_call"
    assert data["name"] == "search"
    assert data["payload"] == {"query": "test"}
    assert data["metadata"] == {"duration_ms": 150}
    assert "id" in data
    assert "timestamp" in data


def test_event_from_dict():
    """Test Event deserialization from dict."""
    data = {
        "type": "llm_invoke",
        "name": "gpt-4",
        "payload": {"prompt": "hello"},
        "metadata": {"tokens": 100},
        "id": "test_id_123",
        "timestamp": "2024-01-01T00:00:00Z",
    }

    event = Event.from_dict(data)

    assert event.type == EventType.LLM_INVOKE
    assert event.name == "gpt-4"
    assert event.payload == {"prompt": "hello"}
    assert event.metadata == {"tokens": 100}
    assert event.id == "test_id_123"
    assert event.timestamp == "2024-01-01T00:00:00Z"


def test_event_roundtrip():
    """Test Event serialization and deserialization roundtrip."""
    original = Event(
        type=EventType.DATA_ACCESS,
        name="database_query",
        payload={"sql": "SELECT * FROM users"},
    )

    data = original.to_dict()
    restored = Event.from_dict(data)

    assert restored.type == original.type
    assert restored.name == original.name
    assert restored.payload == original.payload
    assert restored.id == original.id
    assert restored.timestamp == original.timestamp
