# trusera-sdk-go

Go SDK for monitoring AI agents with Trusera's Cedar-based policy engine.

[![Go Reference](https://pkg.go.dev/badge/github.com/Trusera/trusera-sdk-go.svg)](https://pkg.go.dev/github.com/Trusera/trusera-sdk-go)
[![Go Report Card](https://goreportcard.com/badge/github.com/Trusera/trusera-sdk-go)](https://goreportcard.com/report/github.com/Trusera/trusera-sdk-go)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Zero Dependencies**: Uses only Go standard library
- **HTTP Interception**: Transparently wraps `http.Client` to monitor all outbound requests
- **Policy Enforcement**: Three modes (log, warn, block) for handling policy violations
- **Event Tracking**: Records tool calls, LLM invocations, API calls, file writes, and more
- **Thread-Safe**: Concurrent request handling with proper synchronization
- **Background Flushing**: Automatic batching and periodic event submission

## Installation

```bash
go get github.com/Trusera/trusera-sdk-go
```

## Quickstart

```go
package main

import (
    "fmt"
    "net/http"

    "github.com/Trusera/trusera-sdk-go"
)

func main() {
    // Create Trusera client
    client := trusera.NewClient("your-api-key")
    defer client.Close()

    // Register your agent
    agentID, err := client.RegisterAgent("my-agent", "custom")
    if err != nil {
        panic(err)
    }
    fmt.Println("Agent registered:", agentID)

    // Track an event
    event := trusera.NewEvent(trusera.EventToolCall, "web_search").
        WithPayload("query", "AI security best practices").
        WithPayload("results_count", 10)

    client.Track(event)
}
```

## HTTP Interception

The SDK can wrap Go's `http.Client` to automatically intercept and record all outbound HTTP requests:

```go
package main

import (
    "net/http"
    "github.com/Trusera/trusera-sdk-go"
)

func main() {
    // Create Trusera client
    truseraClient := trusera.NewClient("your-api-key",
        trusera.WithAgentID("agent-123"))
    defer truseraClient.Close()

    // Wrap HTTP client with interception
    httpClient := trusera.WrapHTTPClient(&http.Client{}, truseraClient, trusera.InterceptorOptions{
        Enforcement: trusera.ModeBlock,
        BlockPatterns: []string{"malicious.com", "blocked-api.io"},
        ExcludePatterns: []string{"api.trusera.io"}, // Don't intercept Trusera API calls
    })

    // All requests are now monitored and enforced
    resp, err := httpClient.Get("https://api.example.com/data")
    if err != nil {
        // Request may be blocked by policy
        panic(err)
    }
    defer resp.Body.Close()
}
```

### Convenience Helper

For quick setup with registration and interception:

```go
truseraClient, httpClient, err := trusera.MustRegisterAndIntercept(
    "your-api-key",
    "my-agent",
    "langchain",
    trusera.InterceptorOptions{
        Enforcement: trusera.ModeWarn,
    },
)
if err != nil {
    panic(err)
}
defer truseraClient.Close()

// Use httpClient for all requests
resp, _ := httpClient.Get("https://api.openai.com/v1/chat/completions")
```

## Enforcement Modes

The SDK supports three enforcement modes for handling policy violations:

### Log Mode (Default)

Records all requests silently without blocking:

```go
opts := trusera.InterceptorOptions{
    Enforcement: trusera.ModeLog,
    BlockPatterns: []string{"restricted.com"}, // Recorded but allowed
}
```

### Warn Mode

Logs warnings for blocked patterns but allows requests to proceed:

```go
opts := trusera.InterceptorOptions{
    Enforcement: trusera.ModeWarn,
    BlockPatterns: []string{"suspicious.com"},
}
// Request proceeds, warning recorded in Trusera
```

### Block Mode

Rejects requests matching block patterns with HTTP 403:

```go
opts := trusera.InterceptorOptions{
    Enforcement: trusera.ModeBlock,
    BlockPatterns: []string{"malicious.com"},
}
// Request returns error, backend never called
```

## Event Types

The SDK supports tracking various agent actions:

```go
// Tool calls
event := trusera.NewEvent(trusera.EventToolCall, "calculator").
    WithPayload("operation", "multiply").
    WithPayload("args", []int{5, 7})

// LLM invocations
event := trusera.NewEvent(trusera.EventLLMInvoke, "gpt-4").
    WithPayload("prompt_tokens", 150).
    WithPayload("completion_tokens", 75)

// Data access
event := trusera.NewEvent(trusera.EventDataAccess, "database_query").
    WithPayload("query", "SELECT * FROM users").
    WithPayload("rows_returned", 42)

// File writes
event := trusera.NewEvent(trusera.EventFileWrite, "save_report").
    WithPayload("path", "/tmp/report.pdf").
    WithPayload("size_bytes", 1024)

// API calls (auto-tracked by interceptor)
event := trusera.NewEvent(trusera.EventAPICall, "POST https://api.stripe.com/v1/charges")

// Decisions
event := trusera.NewEvent(trusera.EventDecision, "approve_transaction").
    WithPayload("confidence", 0.95).
    WithPayload("reasoning", "All fraud checks passed")
```

## Configuration Options

### Client Options

```go
client := trusera.NewClient("api-key",
    trusera.WithBaseURL("https://custom.trusera.io"),
    trusera.WithAgentID("agent-123"),
    trusera.WithFlushInterval(60*time.Second),
    trusera.WithBatchSize(200),
)
```

### Interceptor Options

```go
opts := trusera.InterceptorOptions{
    Enforcement: trusera.ModeBlock,

    // URLs matching these patterns won't be intercepted
    ExcludePatterns: []string{
        "api.trusera.io",
        "localhost",
        "127.0.0.1",
    },

    // URLs matching these patterns trigger policy enforcement
    BlockPatterns: []string{
        "malicious.com",
        "blocked-api.io",
        "/internal/admin",
    },
}
```

## Intercept Global Default Client

To intercept all HTTP requests using `http.DefaultClient`:

```go
truseraClient := trusera.NewClient("api-key")
defer truseraClient.Close()

// Wrap the default client
trusera.InterceptDefault(truseraClient, trusera.InterceptorOptions{
    Enforcement: trusera.ModeLog,
})

// Now all http.Get, http.Post, etc. are intercepted
resp, _ := http.Get("https://api.example.com")
```

**Warning**: This affects all code using `http.DefaultClient` globally.

## Manual Flushing

Events are automatically flushed based on batch size and interval, but you can force a flush:

```go
client := trusera.NewClient("api-key")

// Track events
client.Track(event1)
client.Track(event2)

// Force immediate send
if err := client.Flush(); err != nil {
    log.Printf("Failed to flush events: %v", err)
}
```

## Thread Safety

The SDK is safe for concurrent use. Multiple goroutines can call `Track()` simultaneously:

```go
client := trusera.NewClient("api-key")
defer client.Close()

var wg sync.WaitGroup
for i := 0; i < 100; i++ {
    wg.Add(1)
    go func(id int) {
        defer wg.Done()
        event := trusera.NewEvent(trusera.EventToolCall, fmt.Sprintf("tool-%d", id))
        client.Track(event)
    }(i)
}
wg.Wait()
```

## Testing

Run the test suite:

```bash
go test -v ./...
```

Run with race detection:

```bash
go test -race ./...
```

## Examples

See the [examples](./examples) directory for complete working examples:

- Basic tracking
- HTTP interception with different enforcement modes
- Integration with popular frameworks

## Contributing

Contributions welcome! Please read our [Contributing Guide](../CONTRIBUTING.md).

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Links

- [Trusera Platform](https://trusera.io)
- [Documentation](https://docs.trusera.io)
- [API Reference](https://pkg.go.dev/github.com/Trusera/trusera-sdk-go)
- [Go SDK Repository](https://github.com/Trusera/trusera-sdk-go)
