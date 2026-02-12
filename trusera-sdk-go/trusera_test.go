package trusera

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

func TestNewClient(t *testing.T) {
	client := NewClient("test-api-key")
	defer client.Close()

	if client.apiKey != "test-api-key" {
		t.Errorf("expected apiKey 'test-api-key', got %s", client.apiKey)
	}

	if client.baseURL != defaultBaseURL {
		t.Errorf("expected baseURL %s, got %s", defaultBaseURL, client.baseURL)
	}

	if client.flushSize != defaultBatchSize {
		t.Errorf("expected flushSize %d, got %d", defaultBatchSize, client.flushSize)
	}
}

func TestClientWithOptions(t *testing.T) {
	customURL := "https://custom.api.com"
	customAgent := "agent-123"
	customBatch := 50

	client := NewClient(
		"test-key",
		WithBaseURL(customURL),
		WithAgentID(customAgent),
		WithBatchSize(customBatch),
	)
	defer client.Close()

	if client.baseURL != customURL {
		t.Errorf("expected baseURL %s, got %s", customURL, client.baseURL)
	}

	if client.agentID != customAgent {
		t.Errorf("expected agentID %s, got %s", customAgent, client.agentID)
	}

	if client.flushSize != customBatch {
		t.Errorf("expected flushSize %d, got %d", customBatch, client.flushSize)
	}
}

func TestTrackEvent(t *testing.T) {
	client := NewClient("test-key")
	defer client.Close()

	event := NewEvent(EventToolCall, "test-tool")

	client.Track(event)

	client.mu.Lock()
	if len(client.events) != 1 {
		t.Errorf("expected 1 event, got %d", len(client.events))
	}
	client.mu.Unlock()
}

func TestFlush(t *testing.T) {
	var receivedEvents []Event
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/events" {
			t.Errorf("unexpected path: %s", r.URL.Path)
			w.WriteHeader(http.StatusNotFound)
			return
		}

		if r.Header.Get("Authorization") != "Bearer test-key" {
			t.Errorf("missing or invalid Authorization header")
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		var payload struct {
			AgentID string  `json:"agent_id"`
			Events  []Event `json:"events"`
		}

		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Errorf("failed to decode payload: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			return
		}

		mu.Lock()
		receivedEvents = append(receivedEvents, payload.Events...)
		mu.Unlock()

		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient("test-key", WithBaseURL(server.URL))
	defer client.Close()

	event1 := NewEvent(EventToolCall, "tool1")
	event2 := NewEvent(EventAPICall, "api1")

	client.Track(event1)
	client.Track(event2)

	err := client.Flush()
	if err != nil {
		t.Errorf("Flush failed: %v", err)
	}

	mu.Lock()
	if len(receivedEvents) != 2 {
		t.Errorf("expected 2 events, got %d", len(receivedEvents))
	}
	mu.Unlock()

	client.mu.Lock()
	if len(client.events) != 0 {
		t.Errorf("expected events to be cleared after flush, got %d", len(client.events))
	}
	client.mu.Unlock()
}

func TestRegisterAgent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/agents" {
			w.WriteHeader(http.StatusNotFound)
			return
		}

		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		var payload struct {
			Name      string `json:"name"`
			Framework string `json:"framework"`
		}

		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			return
		}

		if payload.Name != "test-agent" {
			t.Errorf("expected name 'test-agent', got %s", payload.Name)
		}

		if payload.Framework != "langchain" {
			t.Errorf("expected framework 'langchain', got %s", payload.Framework)
		}

		response := map[string]string{
			"agent_id": "agent-abc-123",
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test-key", WithBaseURL(server.URL))
	defer client.Close()

	agentID, err := client.RegisterAgent("test-agent", "langchain")
	if err != nil {
		t.Fatalf("RegisterAgent failed: %v", err)
	}

	if agentID != "agent-abc-123" {
		t.Errorf("expected agentID 'agent-abc-123', got %s", agentID)
	}

	if client.agentID != agentID {
		t.Errorf("client agentID not updated")
	}
}

func TestRegisterAgentEmptyName(t *testing.T) {
	client := NewClient("test-key")
	defer client.Close()

	_, err := client.RegisterAgent("", "framework")
	if err == nil {
		t.Error("expected error for empty agent name")
	}
}

func TestBackgroundFlusher(t *testing.T) {
	var flushCount int
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		flushCount++
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(
		"test-key",
		WithBaseURL(server.URL),
		WithFlushInterval(100*time.Millisecond),
	)

	event := NewEvent(EventToolCall, "test")
	client.Track(event)

	time.Sleep(250 * time.Millisecond)

	client.Close()

	mu.Lock()
	if flushCount < 1 {
		t.Errorf("expected at least 1 background flush, got %d", flushCount)
	}
	mu.Unlock()
}

func TestBatchAutoFlush(t *testing.T) {
	var receivedCount int
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload struct {
			Events []Event `json:"events"`
		}
		json.NewDecoder(r.Body).Decode(&payload)

		mu.Lock()
		receivedCount += len(payload.Events)
		mu.Unlock()

		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(
		"test-key",
		WithBaseURL(server.URL),
		WithBatchSize(5),
	)
	defer client.Close()

	for i := 0; i < 10; i++ {
		event := NewEvent(EventToolCall, "tool")
		client.Track(event)
	}

	time.Sleep(100 * time.Millisecond)

	mu.Lock()
	if receivedCount < 5 {
		t.Errorf("expected at least 5 events auto-flushed, got %d", receivedCount)
	}
	mu.Unlock()
}

func TestClose(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient("test-key", WithBaseURL(server.URL))

	event := NewEvent(EventToolCall, "test")
	client.Track(event)

	err := client.Close()
	if err != nil {
		t.Errorf("Close failed: %v", err)
	}

	client.mu.Lock()
	eventCount := len(client.events)
	client.mu.Unlock()

	if eventCount != 0 {
		t.Errorf("expected events to be flushed on close, got %d remaining", eventCount)
	}
}
