# Examples

This directory contains example programs demonstrating various features of the Trusera Go SDK.

## Running the Examples

Each example is a standalone Go program. To run them:

```bash
cd examples/basic
go run main.go
```

Replace `"your-api-key"` in the code with your actual Trusera API key.

## Examples

### 1. Basic Event Tracking

**File**: `basic/main.go`

Demonstrates:
- Creating a Trusera client
- Tracking different event types (tool calls, LLM invocations, data access, decisions)
- Using the builder pattern for events
- Manual flushing

### 2. HTTP Interceptor

**File**: `http-interceptor/main.go`

Demonstrates:
- Wrapping an HTTP client with Trusera interception
- Warn mode enforcement
- Exclude patterns to skip certain URLs
- Block patterns for policy evaluation
- POST requests with bodies

### 3. Block Mode

**File**: `block-mode/main.go`

Demonstrates:
- Block mode enforcement (rejecting blocked requests)
- Agent registration and HTTP interception in one call
- Handling blocked request errors
- Multiple block patterns

## Configuration

All examples use placeholder API keys. Before running:

1. Sign up at https://trusera.io
2. Get your API key from the dashboard
3. Replace `"your-api-key"` in the example code

## Notes

- Examples use public APIs that may have rate limits
- Block mode examples use fake domains for demonstration
- All events are sent to the Trusera API for analysis and compliance reporting
