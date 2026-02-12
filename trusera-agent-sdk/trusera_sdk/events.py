"""Event types and data structures for Trusera SDK."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of events that can be tracked by Trusera."""

    TOOL_CALL = "tool_call"
    LLM_INVOKE = "llm_invoke"
    DATA_ACCESS = "data_access"
    API_CALL = "api_call"
    FILE_WRITE = "file_write"
    DECISION = "decision"


@dataclass
class Event:
    """
    Represents a single event in an AI agent's execution.

    Attributes:
        type: The type of event (tool call, LLM invocation, etc.)
        name: Human-readable name of the event
        payload: Event-specific data (inputs, outputs, etc.)
        metadata: Additional context (duration, model, etc.)
        id: Unique identifier for the event
        timestamp: ISO 8601 timestamp of when the event occurred
    """

    type: EventType
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create an Event from a dictionary."""
        return cls(
            type=EventType(data["type"]),
            name=data["name"],
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            id=data.get("id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
