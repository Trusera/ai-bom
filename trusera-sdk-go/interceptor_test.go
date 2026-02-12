package trusera

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestWrapHTTPClient(t *testing.T) {
	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement: ModeLog,
	})

	if httpClient == nil {
		t.Fatal("expected non-nil http client")
	}

	if httpClient.Transport == nil {
		t.Fatal("expected non-nil transport")
	}

	_, ok := httpClient.Transport.(*interceptingTransport)
	if !ok {
		t.Error("expected transport to be interceptingTransport")
	}
}

func TestInterceptorRecordsRequests(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("success"))
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement: ModeLog,
	})

	resp, err := httpClient.Get(backend.URL + "/test")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	time.Sleep(50 * time.Millisecond)

	truseraClient.mu.Lock()
	eventCount := len(truseraClient.events)
	truseraClient.mu.Unlock()

	if eventCount < 1 {
		t.Errorf("expected at least 1 event recorded, got %d", eventCount)
	}
}

func TestExcludePatterns(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement:     ModeLog,
		ExcludePatterns: []string{"localhost", "127.0.0.1"},
	})

	resp, err := httpClient.Get(backend.URL + "/excluded")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	time.Sleep(50 * time.Millisecond)

	truseraClient.mu.Lock()
	eventCount := len(truseraClient.events)
	truseraClient.mu.Unlock()

	if eventCount > 0 {
		t.Errorf("expected 0 events for excluded URL, got %d", eventCount)
	}
}

func TestBlockModeRejectsRequests(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("backend should not be called for blocked request")
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement:   ModeBlock,
		BlockPatterns: []string{"/blocked"},
	})

	resp, err := httpClient.Get(backend.URL + "/blocked/resource")
	if err == nil {
		t.Error("expected error for blocked request")
	}

	if !strings.Contains(err.Error(), "blocked by Trusera policy") {
		t.Errorf("expected policy error message, got: %v", err)
	}

	if resp != nil {
		resp.Body.Close()
	}
}

func TestWarnModeAllowsBlockedRequests(t *testing.T) {
	backendCalled := false
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		backendCalled = true
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement:   ModeWarn,
		BlockPatterns: []string{"/blocked"},
	})

	resp, err := httpClient.Get(backend.URL + "/blocked/resource")
	if err != nil {
		t.Fatalf("request should succeed in warn mode: %v", err)
	}
	resp.Body.Close()

	if !backendCalled {
		t.Error("backend should be called in warn mode")
	}

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected status 200, got %d", resp.StatusCode)
	}
}

func TestLogModeAllowsAllRequests(t *testing.T) {
	backendCalled := false
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		backendCalled = true
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement:   ModeLog,
		BlockPatterns: []string{"/blocked"},
	})

	resp, err := httpClient.Get(backend.URL + "/blocked/resource")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	if !backendCalled {
		t.Error("backend should be called in log mode")
	}
}

func TestSanitizeHeaders(t *testing.T) {
	headers := http.Header{
		"Content-Type":  []string{"application/json"},
		"Authorization": []string{"Bearer secret-token"},
		"Cookie":        []string{"session=abc123"},
		"X-Api-Key":     []string{"key-123"},
		"User-Agent":    []string{"test-agent"},
	}

	sanitized := sanitizeHeaders(headers)

	if sanitized["Content-Type"] != "application/json" {
		t.Error("Content-Type should not be redacted")
	}

	if sanitized["User-Agent"] != "test-agent" {
		t.Error("User-Agent should not be redacted")
	}

	if sanitized["Authorization"] != "[REDACTED]" {
		t.Error("Authorization should be redacted")
	}

	if sanitized["Cookie"] != "[REDACTED]" {
		t.Error("Cookie should be redacted")
	}

	if sanitized["X-Api-Key"] != "[REDACTED]" {
		t.Error("X-Api-Key should be redacted")
	}
}

func TestRequestBodyCapture(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if string(body) != `{"test":"data"}` {
			t.Errorf("backend received wrong body: %s", string(body))
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement: ModeLog,
	})

	req, _ := http.NewRequest("POST", backend.URL+"/api", strings.NewReader(`{"test":"data"}`))
	req.Header.Set("Content-Type", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()
}

func TestCreateInterceptedClient(t *testing.T) {
	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := CreateInterceptedClient(truseraClient, InterceptorOptions{
		Enforcement: ModeLog,
	})

	if httpClient == nil {
		t.Fatal("expected non-nil client")
	}

	_, ok := httpClient.Transport.(*interceptingTransport)
	if !ok {
		t.Error("expected intercepting transport")
	}
}

func TestConcurrentRequests(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(10 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	truseraServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer truseraServer.Close()

	truseraClient := NewClient("test-key", WithBaseURL(truseraServer.URL))
	defer truseraClient.Close()

	httpClient := WrapHTTPClient(&http.Client{}, truseraClient, InterceptorOptions{
		Enforcement: ModeLog,
	})

	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			resp, err := httpClient.Get(backend.URL)
			if err != nil {
				t.Errorf("concurrent request failed: %v", err)
				return
			}
			resp.Body.Close()
		}()
	}

	wg.Wait()
}
