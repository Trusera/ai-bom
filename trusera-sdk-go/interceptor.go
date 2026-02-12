package trusera

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const maxBodySnippet = 500

// EnforcementMode determines how policy violations are handled
type EnforcementMode string

const (
	ModeLog   EnforcementMode = "log"   // Record but allow all requests
	ModeWarn  EnforcementMode = "warn"  // Log warnings for blocked patterns but allow
	ModeBlock EnforcementMode = "block" // Reject blocked requests with error
)

// InterceptorOptions configures the HTTP interceptor
type InterceptorOptions struct {
	Enforcement     EnforcementMode
	ExcludePatterns []string // URL patterns to skip interception
	BlockPatterns   []string // URL patterns to block (for testing enforcement)
}

// WrapHTTPClient wraps an http.Client to intercept all outbound requests
func WrapHTTPClient(client *http.Client, truseraClient *Client, opts InterceptorOptions) *http.Client {
	if client == nil {
		client = &http.Client{}
	}

	transport := client.Transport
	if transport == nil {
		transport = http.DefaultTransport
	}

	client.Transport = &interceptingTransport{
		base:   transport,
		client: truseraClient,
		opts:   opts,
	}

	return client
}

// interceptingTransport wraps http.RoundTripper
type interceptingTransport struct {
	base   http.RoundTripper
	client *Client
	opts   InterceptorOptions
}

// RoundTrip intercepts and records HTTP requests
func (t *interceptingTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	// Check if URL should be excluded from interception
	if t.shouldExclude(req.URL.String()) {
		return t.base.RoundTrip(req)
	}

	// Check if URL matches block patterns (for enforcement)
	blocked := t.isBlocked(req.URL.String())

	// Read and restore request body for logging
	var bodySnippet string
	if req.Body != nil {
		bodyBytes, err := io.ReadAll(req.Body)
		if err == nil {
			req.Body.Close()
			req.Body = io.NopCloser(bytes.NewReader(bodyBytes))

			if len(bodyBytes) > maxBodySnippet {
				bodySnippet = string(bodyBytes[:maxBodySnippet]) + "..."
			} else {
				bodySnippet = string(bodyBytes)
			}
		}
	}

	// Create event for this API call
	event := NewEvent(EventAPICall, req.Method+" "+req.URL.String()).
		WithPayload("method", req.Method).
		WithPayload("url", req.URL.String()).
		WithPayload("headers", sanitizeHeaders(req.Header)).
		WithPayload("blocked", blocked).
		WithMetadata("enforcement_mode", string(t.opts.Enforcement))

	if bodySnippet != "" {
		event = event.WithPayload("body_snippet", bodySnippet)
	}

	// Handle enforcement modes
	if blocked {
		event = event.WithPayload("enforcement_action", "blocked")

		switch t.opts.Enforcement {
		case ModeBlock:
			t.client.Track(event)
			return nil, errors.New("request blocked by Trusera policy")

		case ModeWarn:
			event = event.WithMetadata("warning", "URL matches block pattern but allowed in warn mode")
			t.client.Track(event)
			// Continue with request

		case ModeLog:
			// Just record, no action
			t.client.Track(event)
		}
	} else {
		event = event.WithPayload("enforcement_action", "allowed")
		t.client.Track(event)
	}

	// Forward request to base transport
	resp, err := t.base.RoundTrip(req)
	if err != nil {
		// Track the error
		errorEvent := NewEvent(EventAPICall, "error").
			WithPayload("method", req.Method).
			WithPayload("url", req.URL.String()).
			WithPayload("error", err.Error())
		t.client.Track(errorEvent)
		return resp, err
	}

	// Record response status
	responseEvent := NewEvent(EventAPICall, "response").
		WithPayload("method", req.Method).
		WithPayload("url", req.URL.String()).
		WithPayload("status_code", resp.StatusCode).
		WithPayload("status", resp.Status)
	t.client.Track(responseEvent)

	return resp, nil
}

// shouldExclude checks if URL matches any exclude patterns
func (t *interceptingTransport) shouldExclude(url string) bool {
	for _, pattern := range t.opts.ExcludePatterns {
		if strings.Contains(url, pattern) {
			return true
		}
	}
	return false
}

// isBlocked checks if URL matches any block patterns
func (t *interceptingTransport) isBlocked(url string) bool {
	for _, pattern := range t.opts.BlockPatterns {
		if strings.Contains(url, pattern) {
			return true
		}
	}
	return false
}

// sanitizeHeaders removes sensitive headers from logging
func sanitizeHeaders(headers http.Header) map[string]string {
	sanitized := make(map[string]string)
	sensitiveHeaders := map[string]bool{
		"authorization": true,
		"cookie":        true,
		"set-cookie":    true,
		"x-api-key":     true,
	}

	for key, values := range headers {
		lowerKey := strings.ToLower(key)
		if sensitiveHeaders[lowerKey] {
			sanitized[key] = "[REDACTED]"
		} else if len(values) > 0 {
			sanitized[key] = values[0]
		}
	}

	return sanitized
}

// CreateInterceptedClient creates a new http.Client with Trusera interception
func CreateInterceptedClient(truseraClient *Client, opts InterceptorOptions) *http.Client {
	return WrapHTTPClient(&http.Client{}, truseraClient, opts)
}

// InterceptDefault wraps http.DefaultClient with Trusera interception
func InterceptDefault(truseraClient *Client, opts InterceptorOptions) {
	http.DefaultClient = WrapHTTPClient(http.DefaultClient, truseraClient, opts)
}

// MustRegisterAndIntercept is a convenience function that registers an agent and returns an intercepted client
func MustRegisterAndIntercept(apiKey, agentName, framework string, opts InterceptorOptions) (*Client, *http.Client, error) {
	client := NewClient(apiKey)

	_, err := client.RegisterAgent(agentName, framework)
	if err != nil {
		client.Close()
		return nil, nil, fmt.Errorf("failed to register agent: %w", err)
	}

	httpClient := CreateInterceptedClient(client, opts)

	return client, httpClient, nil
}
