package trusera

import (
	"encoding/json"
	"testing"
	"time"
)

func TestNewEvent(t *testing.T) {
	event := NewEvent(EventToolCall, "test-tool")

	if event.ID == "" {
		t.Error("expected non-empty event ID")
	}

	if event.Type != EventToolCall {
		t.Errorf("expected type %s, got %s", EventToolCall, event.Type)
	}

	if event.Name != "test-tool" {
		t.Errorf("expected name 'test-tool', got %s", event.Name)
	}

	if event.Payload == nil {
		t.Error("expected non-nil payload")
	}

	if event.Metadata == nil {
		t.Error("expected non-nil metadata")
	}

	if event.Timestamp == "" {
		t.Error("expected non-empty timestamp")
	}

	_, err := time.Parse(time.RFC3339, event.Timestamp)
	if err != nil {
		t.Errorf("invalid timestamp format: %v", err)
	}
}

func TestWithPayload(t *testing.T) {
	event := NewEvent(EventAPICall, "http-get").
		WithPayload("url", "https://api.example.com").
		WithPayload("method", "GET").
		WithPayload("status", 200)

	if event.Payload["url"] != "https://api.example.com" {
		t.Errorf("expected url in payload, got %v", event.Payload["url"])
	}

	if event.Payload["method"] != "GET" {
		t.Errorf("expected method in payload, got %v", event.Payload["method"])
	}

	if event.Payload["status"] != 200 {
		t.Errorf("expected status in payload, got %v", event.Payload["status"])
	}
}

func TestWithMetadata(t *testing.T) {
	event := NewEvent(EventToolCall, "test").
		WithMetadata("user_id", "user-123").
		WithMetadata("session_id", "sess-456")

	if event.Metadata["user_id"] != "user-123" {
		t.Errorf("expected user_id in metadata, got %v", event.Metadata["user_id"])
	}

	if event.Metadata["session_id"] != "sess-456" {
		t.Errorf("expected session_id in metadata, got %v", event.Metadata["session_id"])
	}
}

func TestEventSerialization(t *testing.T) {
	event := NewEvent(EventLLMInvoke, "gpt-4").
		WithPayload("model", "gpt-4-turbo").
		WithPayload("tokens", 150).
		WithMetadata("temperature", 0.7)

	data, err := json.Marshal(event)
	if err != nil {
		t.Fatalf("failed to marshal event: %v", err)
	}

	var decoded Event
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("failed to unmarshal event: %v", err)
	}

	if decoded.ID != event.ID {
		t.Errorf("ID mismatch: expected %s, got %s", event.ID, decoded.ID)
	}

	if decoded.Type != event.Type {
		t.Errorf("Type mismatch: expected %s, got %s", event.Type, decoded.Type)
	}

	if decoded.Name != event.Name {
		t.Errorf("Name mismatch: expected %s, got %s", event.Name, decoded.Name)
	}

	if decoded.Payload["model"] != "gpt-4-turbo" {
		t.Errorf("Payload model mismatch")
	}

	if decoded.Metadata["temperature"] != 0.7 {
		t.Errorf("Metadata temperature mismatch")
	}
}

func TestEventTypes(t *testing.T) {
	types := []EventType{
		EventToolCall,
		EventLLMInvoke,
		EventDataAccess,
		EventAPICall,
		EventFileWrite,
		EventDecision,
	}

	for _, eventType := range types {
		event := NewEvent(eventType, "test")
		if event.Type != eventType {
			t.Errorf("event type mismatch for %s", eventType)
		}
	}
}

func TestUniqueEventIDs(t *testing.T) {
	ids := make(map[string]bool)

	for i := 0; i < 1000; i++ {
		event := NewEvent(EventToolCall, "test")
		if ids[event.ID] {
			t.Errorf("duplicate event ID generated: %s", event.ID)
		}
		ids[event.ID] = true
	}
}

func TestChainedBuilderPattern(t *testing.T) {
	event := NewEvent(EventDataAccess, "database-query").
		WithPayload("query", "SELECT * FROM users").
		WithPayload("database", "postgres").
		WithMetadata("user", "admin").
		WithMetadata("ip", "192.168.1.1")

	if len(event.Payload) != 2 {
		t.Errorf("expected 2 payload entries, got %d", len(event.Payload))
	}

	if len(event.Metadata) != 2 {
		t.Errorf("expected 2 metadata entries, got %d", len(event.Metadata))
	}
}
