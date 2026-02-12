# Quick Start Guide

Get started with the Trusera Go SDK in 5 minutes.

## Installation

```bash
go get github.com/Trusera/trusera-sdk-go
```

## Your First Trusera Agent

Create a file `main.go`:

```go
package main

import (
    "fmt"
    "net/http"

    "github.com/Trusera/trusera-sdk-go"
)

func main() {
    // 1. Create Trusera client
    client := trusera.NewClient("your-api-key-here")
    defer client.Close()

    // 2. Register your agent
    agentID, err := client.RegisterAgent("my-first-agent", "custom")
    if err != nil {
        panic(err)
    }
    fmt.Println("Agent registered:", agentID)

    // 3. Track events
    event := trusera.NewEvent(trusera.EventToolCall, "calculator").
        WithPayload("operation", "add").
        WithPayload("result", 42)

    client.Track(event)
    fmt.Println("Event tracked!")
}
```

Run it:

```bash
go run main.go
```

## Adding HTTP Interception

Wrap your HTTP client to automatically monitor all outbound requests:

```go
package main

import (
    "fmt"
    "net/http"

    "github.com/Trusera/trusera-sdk-go"
)

func main() {
    // Create client
    client := trusera.NewClient("your-api-key")
    defer client.Close()

    // Wrap HTTP client
    httpClient := trusera.WrapHTTPClient(&http.Client{}, client,
        trusera.InterceptorOptions{
            Enforcement: trusera.ModeLog,
        })

    // All requests are now monitored
    resp, _ := httpClient.Get("https://api.github.com")
    defer resp.Body.Close()

    fmt.Println("Request monitored and logged to Trusera")
}
```

## Blocking Malicious Requests

Use block mode to enforce security policies:

```go
package main

import (
    "fmt"
    "github.com/Trusera/trusera-sdk-go"
)

func main() {
    // Register and intercept in one call
    client, httpClient, _ := trusera.MustRegisterAndIntercept(
        "your-api-key",
        "security-agent",
        "custom",
        trusera.InterceptorOptions{
            Enforcement: trusera.ModeBlock,
            BlockPatterns: []string{
                "malicious.com",
                "phishing.net",
            },
        },
    )
    defer client.Close()

    // This will be blocked
    _, err := httpClient.Get("https://malicious.com/steal-data")
    if err != nil {
        fmt.Println("Request blocked:", err)
    }
}
```

## Next Steps

- Read the [full documentation](README.md)
- Explore [examples](examples/)
- Learn about [enforcement modes](README.md#enforcement-modes)
- Check out [event types](README.md#event-types)

## Getting Your API Key

1. Sign up at https://trusera.io
2. Create a project
3. Copy your API key from the dashboard
4. Replace `"your-api-key"` in the examples

## Support

- Documentation: https://docs.trusera.io
- Issues: https://github.com/Trusera/trusera-sdk-go/issues
- Discord: https://discord.gg/trusera
