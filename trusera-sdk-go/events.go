package trusera

import (
	"crypto/rand"
	"encoding/hex"
	"time"
)

// EventType defines the type of agent event
type EventType string

const (
	EventToolCall   EventType = "tool_call"
	EventLLMInvoke  EventType = "llm_invoke"
	EventDataAccess EventType = "data_access"
	EventAPICall    EventType = "api_call"
	EventFileWrite  EventType = "file_write"
	EventDecision   EventType = "decision"
)

// Event represents an agent action tracked by Trusera
type Event struct {
	ID        string         `json:"id"`
	Type      EventType      `json:"type"`
	Name      string         `json:"name"`
	Payload   map[string]any `json:"payload"`
	Metadata  map[string]any `json:"metadata,omitempty"`
	Timestamp string         `json:"timestamp"`
}

// generateID creates a random hex ID
func generateID() string {
	b := make([]byte, 16)
	rand.Read(b)
	return hex.EncodeToString(b)
}

// NewEvent creates a new event with generated ID and timestamp
func NewEvent(eventType EventType, name string) Event {
	return Event{
		ID:        generateID(),
		Type:      eventType,
		Name:      name,
		Payload:   make(map[string]any),
		Metadata:  make(map[string]any),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
}

// WithPayload adds payload data to the event (builder pattern)
func (e Event) WithPayload(key string, value any) Event {
	if e.Payload == nil {
		e.Payload = make(map[string]any)
	}
	e.Payload[key] = value
	return e
}

// WithMetadata adds metadata to the event (builder pattern)
func (e Event) WithMetadata(key string, value any) Event {
	if e.Metadata == nil {
		e.Metadata = make(map[string]any)
	}
	e.Metadata[key] = value
	return e
}
