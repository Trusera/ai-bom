# Trusera SDK for JavaScript/TypeScript

[![npm version](https://badge.fury.io/js/trusera-sdk.svg)](https://www.npmjs.com/package/trusera-sdk)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

The official TypeScript/JavaScript SDK for monitoring AI agents with [Trusera](https://trusera.io). Provides transparent HTTP interception, policy enforcement, and comprehensive observability for AI agent applications.

## Key Features

- **Transparent HTTP Interception**: Zero-code instrumentation of all outbound HTTP calls
- **Policy Enforcement**: Runtime evaluation against Cedar policies with configurable enforcement modes
- **LangChain.js Integration**: First-class support for LangChain.js callbacks
- **Rich Event Tracking**: Track LLM calls, tool executions, data access, and custom events
- **Batched Transmission**: Automatic event batching and retry logic
- **Type-Safe**: Full TypeScript support with strict typing

## Installation

```bash
npm install trusera-sdk
```

## Quick Start

### Basic Usage (HTTP Interceptor)

The simplest way to get started is with the HTTP interceptor:

```typescript
import { TruseraClient, TruseraInterceptor } from "trusera-sdk";

// Create client
const client = new TruseraClient({
  apiKey: "tsk_your_api_key_here",
  agentId: "my-agent-123",
});

// Install interceptor
const interceptor = new TruseraInterceptor();
interceptor.install(client, {
  enforcement: "log", // or "warn" or "block"
});

// All fetch calls are now automatically tracked
await fetch("https://api.github.com/repos/anthropics/claude");
await fetch("https://api.openai.com/v1/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ model: "gpt-4", messages: [] }),
});

// Cleanup
await client.close();
interceptor.uninstall();
```

### LangChain.js Integration

Track LLM calls, tool executions, and chain steps automatically:

```typescript
import { ChatOpenAI } from "langchain/chat_models/openai";
import { TruseraClient, TruseraLangChainHandler } from "trusera-sdk";

const client = new TruseraClient({ apiKey: "tsk_xxx" });
const handler = new TruseraLangChainHandler(client);

const model = new ChatOpenAI({
  callbacks: [handler],
});

await model.invoke("What are the top AI security risks?");

await client.close();
```

### Manual Event Tracking

For custom instrumentation:

```typescript
import { TruseraClient, EventType, createEvent } from "trusera-sdk";

const client = new TruseraClient({ apiKey: "tsk_xxx" });

// Track tool call
client.track(
  createEvent(EventType.TOOL_CALL, "github.search_repos", {
    query: "AI security",
    language: "TypeScript",
  })
);

// Track LLM invocation
client.track(
  createEvent(EventType.LLM_INVOKE, "openai.gpt4", {
    model: "gpt-4",
    tokens: 150,
    temperature: 0.7,
  })
);

// Track data access
client.track(
  createEvent(EventType.DATA_ACCESS, "database.users.read", {
    table: "users",
    query: "SELECT * FROM users WHERE id = ?",
  })
);

await client.close();
```

## Configuration

### TruseraClient Options

```typescript
interface TruseraClientOptions {
  /** API key for authenticating with Trusera (required) */
  apiKey: string;

  /** Base URL for Trusera API (default: https://api.trusera.io) */
  baseUrl?: string;

  /** Agent identifier (auto-registered if not provided) */
  agentId?: string;

  /** Interval in ms to auto-flush events (default: 5000) */
  flushInterval?: number;

  /** Max events per batch (default: 100) */
  batchSize?: number;

  /** Enable debug logging (default: false) */
  debug?: boolean;
}
```

### Interceptor Options

```typescript
interface InterceptorOptions {
  /** How to handle policy violations (default: "log") */
  enforcement?: "block" | "warn" | "log";

  /** Cedar policy service URL for runtime policy checks */
  policyUrl?: string;

  /** URL patterns to exclude from interception (regex strings) */
  excludePatterns?: string[];

  /** Enable debug logging (default: false) */
  debug?: boolean;
}
```

## Enforcement Modes

The interceptor supports three enforcement modes for policy violations:

### `log` (default)

Logs violations silently, allows all requests to proceed.

```typescript
interceptor.install(client, { enforcement: "log" });
```

### `warn`

Logs warnings to console but allows requests to proceed.

```typescript
interceptor.install(client, { enforcement: "warn" });
// Outputs: [Trusera] Policy violation (allowed): Unauthorized API access
```

### `block`

Throws an error and blocks the request.

```typescript
interceptor.install(client, { enforcement: "block" });
// Throws: Error: [Trusera] Policy violation: Unauthorized API access
```

## Advanced Usage

### Policy-Based Enforcement

Connect to a Cedar policy service for runtime access control:

```typescript
interceptor.install(client, {
  enforcement: "block",
  policyUrl: "https://policy.trusera.io/evaluate",
});

// This request will be evaluated against Cedar policies
// If denied, an error will be thrown before the request executes
await fetch("https://api.stripe.com/v1/customers");
```

### Exclude Internal URLs

Prevent interception of internal or infrastructure URLs:

```typescript
interceptor.install(client, {
  excludePatterns: [
    "^https://api\\.trusera\\.io/.*", // Exclude Trusera API
    "^https://internal\\.company\\.com/.*", // Exclude internal services
    "^http://localhost.*", // Exclude localhost
  ],
});
```

### Agent Registration

Register a new agent programmatically:

```typescript
const client = new TruseraClient({ apiKey: "tsk_xxx" });

const agentId = await client.registerAgent("my-chatbot", "langchain");
console.log(`Agent registered: ${agentId}`);

// Use the returned ID for future sessions
const client2 = new TruseraClient({
  apiKey: "tsk_xxx",
  agentId: agentId,
});
```

### Manual Flush Control

Control when events are sent:

```typescript
const client = new TruseraClient({
  apiKey: "tsk_xxx",
  flushInterval: 999999, // Disable auto-flush
  batchSize: 50,
});

// Track events
client.track(createEvent(EventType.TOOL_CALL, "test"));

// Manually flush when ready
await client.flush();
```

## Event Types

The SDK tracks six core event types:

| Event Type     | Description                              | Example Use Cases                    |
| -------------- | ---------------------------------------- | ------------------------------------ |
| `TOOL_CALL`    | Tool or function call by the agent       | API calls, file operations, searches |
| `LLM_INVOKE`   | LLM inference invocation                 | OpenAI, Anthropic, local models      |
| `DATA_ACCESS`  | Data read/write operations               | Database queries, file I/O           |
| `API_CALL`     | Outbound HTTP API calls                  | Third-party APIs, webhooks           |
| `FILE_WRITE`   | File write operations                    | Log files, cache writes              |
| `DECISION`     | Decision points or chain steps           | Agent reasoning, workflow branches   |

## API Reference

### `TruseraClient`

#### Methods

- `constructor(options: TruseraClientOptions)`: Create a new client
- `track(event: Event): void`: Queue an event for transmission
- `flush(): Promise<void>`: Immediately send all queued events
- `registerAgent(name: string, framework: string): Promise<string>`: Register a new agent
- `close(): Promise<void>`: Flush events and shutdown client
- `getQueueSize(): number`: Get current queue size
- `getAgentId(): string | undefined`: Get the current agent ID

### `TruseraInterceptor`

#### Methods

- `install(client: TruseraClient, options?: InterceptorOptions): void`: Install HTTP interceptor
- `uninstall(): void`: Restore original fetch and remove interceptor

### `TruseraLangChainHandler`

#### Methods

- `constructor(client: TruseraClient)`: Create handler for LangChain callbacks
- `getPendingEventCount(): number`: Get count of incomplete events
- `clearPendingEvents(): void`: Clear all pending events

### Utility Functions

- `createEvent(type: EventType, name: string, payload?, metadata?): Event`: Create a well-formed event
- `isValidEvent(obj: unknown): boolean`: Type guard to validate events

## Examples

### Example: Agent with Tools

```typescript
import { TruseraClient, TruseraInterceptor, EventType, createEvent } from "trusera-sdk";

const client = new TruseraClient({ apiKey: process.env.TRUSERA_API_KEY });
const interceptor = new TruseraInterceptor();

interceptor.install(client, {
  enforcement: "warn",
  excludePatterns: ["^http://localhost.*"],
});

// Tool execution wrapper
async function executeTool(name: string, input: any) {
  const startTime = Date.now();

  try {
    // Tool logic here
    const result = await fetch("https://api.example.com/tool", {
      method: "POST",
      body: JSON.stringify(input),
    });

    const duration = Date.now() - startTime;

    client.track(
      createEvent(EventType.TOOL_CALL, `tool.${name}.success`, {
        input,
        duration_ms: duration,
      })
    );

    return result;
  } catch (error) {
    client.track(
      createEvent(EventType.TOOL_CALL, `tool.${name}.error`, {
        input,
        error: error.message,
      })
    );
    throw error;
  }
}

await executeTool("search", { query: "AI security" });
await client.close();
interceptor.uninstall();
```

### Example: Multi-Agent System

```typescript
const agent1 = new TruseraClient({
  apiKey: "tsk_xxx",
  agentId: "planner",
});

const agent2 = new TruseraClient({
  apiKey: "tsk_xxx",
  agentId: "executor",
});

// Track coordination events
agent1.track(
  createEvent(EventType.DECISION, "coordination.delegate", {
    target_agent: "executor",
    task: "web_search",
  })
);

agent2.track(
  createEvent(EventType.TOOL_CALL, "search.execute", {
    delegated_from: "planner",
  })
);

await Promise.all([agent1.close(), agent2.close()]);
```

## Requirements

- Node.js >= 18.0.0
- TypeScript >= 5.0 (for TypeScript users)

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.

## Support

- Documentation: [https://docs.trusera.io](https://docs.trusera.io)
- Issues: [GitHub Issues](https://github.com/Trusera/trusera-sdk-js/issues)
- Email: support@trusera.io

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Related Projects

- [trusera-sdk-python](https://github.com/Trusera/trusera-sdk-python) - Python SDK
- [ai-bom](https://github.com/Trusera/ai-bom) - AI Bill of Materials scanner
- [trusera-platform](https://github.com/Trusera/trusera-platform) - Full monitoring platform

---

Built with care by the Trusera team. Making AI agents safe and observable.
