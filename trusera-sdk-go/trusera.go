package trusera

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sync"
	"time"
)

const (
	defaultBaseURL       = "https://api.trusera.io"
	defaultFlushInterval = 30 * time.Second
	defaultBatchSize     = 100
)

// Client sends agent events to Trusera API
type Client struct {
	apiKey     string
	baseURL    string
	agentID    string
	httpClient *http.Client
	events     []Event
	mu         sync.Mutex
	flushSize  int
	done       chan struct{}
	ticker     *time.Ticker
	wg         sync.WaitGroup
}

// Option configures a Client
type Option func(*Client)

// WithBaseURL sets the Trusera API base URL
func WithBaseURL(url string) Option {
	return func(c *Client) {
		c.baseURL = url
	}
}

// WithAgentID sets the agent identifier
func WithAgentID(id string) Option {
	return func(c *Client) {
		c.agentID = id
	}
}

// WithFlushInterval sets how often to auto-flush events
func WithFlushInterval(d time.Duration) Option {
	return func(c *Client) {
		if c.ticker != nil {
			c.ticker.Stop()
		}
		c.ticker = time.NewTicker(d)
	}
}

// WithBatchSize sets the max events before auto-flush
func WithBatchSize(n int) Option {
	return func(c *Client) {
		if n > 0 {
			c.flushSize = n
		}
	}
}

// NewClient creates a Trusera monitoring client
func NewClient(apiKey string, opts ...Option) *Client {
	c := &Client{
		apiKey:     apiKey,
		baseURL:    defaultBaseURL,
		httpClient: &http.Client{Timeout: 10 * time.Second},
		events:     make([]Event, 0, defaultBatchSize),
		flushSize:  defaultBatchSize,
		done:       make(chan struct{}),
		ticker:     time.NewTicker(defaultFlushInterval),
	}

	for _, opt := range opts {
		opt(c)
	}

	c.wg.Add(1)
	go c.backgroundFlusher()

	return c
}

// backgroundFlusher periodically flushes events
func (c *Client) backgroundFlusher() {
	defer c.wg.Done()
	for {
		select {
		case <-c.ticker.C:
			_ = c.Flush()
		case <-c.done:
			return
		}
	}
}

// Track queues an event for sending
func (c *Client) Track(event Event) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.events = append(c.events, event)

	if len(c.events) >= c.flushSize {
		go func() {
			_ = c.Flush()
		}()
	}
}

// Flush sends all queued events to the API
func (c *Client) Flush() error {
	c.mu.Lock()
	if len(c.events) == 0 {
		c.mu.Unlock()
		return nil
	}

	events := make([]Event, len(c.events))
	copy(events, c.events)
	c.events = c.events[:0]
	c.mu.Unlock()

	payload := map[string]interface{}{
		"agent_id": c.agentID,
		"events":   events,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal events: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, c.baseURL+"/v1/events", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send events: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	return nil
}

// RegisterAgent registers an agent with Trusera, returns agent ID
func (c *Client) RegisterAgent(name, framework string) (string, error) {
	if name == "" {
		return "", errors.New("agent name is required")
	}

	payload := map[string]string{
		"name":      name,
		"framework": framework,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal payload: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, c.baseURL+"/v1/agents", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to register agent: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var result struct {
		AgentID string `json:"agent_id"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	c.mu.Lock()
	c.agentID = result.AgentID
	c.mu.Unlock()

	return result.AgentID, nil
}

// Close flushes remaining events and stops background goroutine
func (c *Client) Close() error {
	c.ticker.Stop()
	close(c.done)
	c.wg.Wait()

	return c.Flush()
}
