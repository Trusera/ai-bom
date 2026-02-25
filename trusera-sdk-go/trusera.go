package trusera

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"runtime"
	"sync"
	"time"
)

const (
	defaultBaseURL            = "https://api.trusera.io"
	defaultFlushInterval      = 30 * time.Second
	defaultBatchSize          = 100
	defaultHeartbeatInterval  = 60 * time.Second
	sdkVersion                = "1.0.0"
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

	// Fleet auto-registration
	autoRegister      bool
	agentName         string
	agentType         string
	environment       string
	heartbeatInterval time.Duration
	fleetAgentID      string
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

// WithAutoRegister enables fleet auto-registration on startup
func WithAutoRegister() Option {
	return func(c *Client) {
		c.autoRegister = true
	}
}

// WithAgentName sets the agent name for fleet registration
func WithAgentName(name string) Option {
	return func(c *Client) {
		c.agentName = name
	}
}

// WithAgentType sets the agent type for fleet registration
func WithAgentType(t string) Option {
	return func(c *Client) {
		c.agentType = t
	}
}

// WithEnvironment sets the deployment environment for fleet registration
func WithEnvironment(env string) Option {
	return func(c *Client) {
		c.environment = env
	}
}

// WithHeartbeatInterval sets the fleet heartbeat interval
func WithHeartbeatInterval(d time.Duration) Option {
	return func(c *Client) {
		c.heartbeatInterval = d
	}
}

// envOrDefault returns the value of the environment variable named by key,
// or fallback if the variable is not set or empty.
func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// NewClient creates a Trusera monitoring client.
// If apiKey is empty, falls back to the TRUSERA_API_KEY environment variable.
// Base URL defaults to TRUSERA_API_URL env var, then https://api.trusera.io.
// Set TRUSERA_AUTO_REGISTER=true to enable fleet auto-registration via env var.
func NewClient(apiKey string, opts ...Option) *Client {
	if apiKey == "" {
		apiKey = os.Getenv("TRUSERA_API_KEY")
	}

	hostname, _ := os.Hostname()

	c := &Client{
		apiKey:            apiKey,
		baseURL:           envOrDefault("TRUSERA_API_URL", defaultBaseURL),
		httpClient:        &http.Client{Timeout: 10 * time.Second},
		events:            make([]Event, 0, defaultBatchSize),
		flushSize:         defaultBatchSize,
		done:              make(chan struct{}),
		ticker:            time.NewTicker(defaultFlushInterval),
		heartbeatInterval: defaultHeartbeatInterval,
		agentName:         envOrDefault("TRUSERA_AGENT_NAME", hostname),
		agentType:         os.Getenv("TRUSERA_AGENT_TYPE"),
		environment:       os.Getenv("TRUSERA_ENVIRONMENT"),
	}

	for _, opt := range opts {
		opt(c)
	}

	// Env var override for auto-register
	envAuto := os.Getenv("TRUSERA_AUTO_REGISTER")
	if envAuto == "true" || envAuto == "1" {
		c.autoRegister = true
	} else if envAuto == "false" || envAuto == "0" {
		c.autoRegister = false
	}

	// Fleet auto-registration
	if c.autoRegister {
		c.registerWithFleet()
	}

	c.wg.Add(1)
	go c.backgroundFlusher()

	// Start heartbeat if fleet registration succeeded
	if c.fleetAgentID != "" {
		c.wg.Add(1)
		go c.heartbeatLoop()
	}

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

// -- Fleet auto-registration --

func (c *Client) getProcessInfo() map[string]interface{} {
	return map[string]interface{}{
		"pid":        os.Getpid(),
		"args":       os.Args,
		"go_version": runtime.Version(),
		"os":         runtime.GOOS,
		"arch":       runtime.GOARCH,
	}
}

func (c *Client) getNetworkInfo() map[string]interface{} {
	info := map[string]interface{}{}
	hostname, err := os.Hostname()
	if err == nil {
		info["hostname"] = hostname
	}
	addrs, err := net.InterfaceAddrs()
	if err == nil {
		ips := make([]string, 0, len(addrs))
		for _, addr := range addrs {
			if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
				ips = append(ips, ipnet.IP.String())
			}
		}
		if len(ips) > 0 {
			info["ip"] = ips[0]
		}
	}
	return info
}

func (c *Client) registerWithFleet() {
	hostname, _ := os.Hostname()
	payload := map[string]interface{}{
		"name":             c.agentName,
		"discovery_method": "sdk",
		"sdk_version":      sdkVersion,
		"hostname":         hostname,
		"process_info":     c.getProcessInfo(),
		"network_info":     c.getNetworkInfo(),
	}
	if c.agentType != "" {
		payload["framework"] = c.agentType
	}
	if c.environment != "" {
		payload["environment"] = c.environment
	}

	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("[trusera] fleet register marshal error: %v", err)
		return
	}

	req, err := http.NewRequest(http.MethodPost, c.baseURL+"/api/v1/fleet/register", bytes.NewReader(body))
	if err != nil {
		log.Printf("[trusera] fleet register request error: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		log.Printf("[trusera] fleet register failed (continuing without): %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("[trusera] fleet register returned status %d (continuing without)", resp.StatusCode)
		return
	}

	var result struct {
		Data struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Printf("[trusera] fleet register decode error: %v", err)
		return
	}

	if result.Data.ID != "" {
		c.fleetAgentID = result.Data.ID
		log.Printf("[trusera] fleet auto-register succeeded (id=%s)", c.fleetAgentID)
	}
}

func (c *Client) heartbeatLoop() {
	defer c.wg.Done()
	hbTicker := time.NewTicker(c.heartbeatInterval)
	defer hbTicker.Stop()

	for {
		select {
		case <-hbTicker.C:
			c.sendHeartbeat()
		case <-c.done:
			return
		}
	}
}

func (c *Client) sendHeartbeat() {
	if c.fleetAgentID == "" {
		return
	}

	payload := map[string]interface{}{
		"process_info": c.getProcessInfo(),
		"network_info": c.getNetworkInfo(),
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return
	}

	url := fmt.Sprintf("%s/api/v1/fleet/%s/heartbeat", c.baseURL, c.fleetAgentID)
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		log.Printf("[trusera] fleet heartbeat failed: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("[trusera] fleet heartbeat returned status %d", resp.StatusCode)
	}
}

// Close flushes remaining events and stops background goroutine
func (c *Client) Close() error {
	c.ticker.Stop()
	close(c.done)
	c.wg.Wait()

	return c.Flush()
}
