# Trusera SDK - Quick Start Guide

Get started with Trusera SDK in under 5 minutes.

## Installation

```bash
npm install trusera-sdk
```

## 1. Basic Setup (3 lines of code)

```typescript
import { TruseraClient, TruseraInterceptor } from "trusera-sdk";

const client = new TruseraClient({ apiKey: "tsk_your_key" });
const interceptor = new TruseraInterceptor();
interceptor.install(client);

// All fetch calls are now automatically tracked!
```

## 2. Get Your API Key

1. Sign up at [app.trusera.io](https://app.trusera.io)
2. Navigate to Settings → API Keys
3. Create a new API key (starts with `tsk_`)
4. Copy the key

## 3. Run Your First Example

Create `demo.ts`:

```typescript
import { TruseraClient, TruseraInterceptor } from "trusera-sdk";

const client = new TruseraClient({
  apiKey: "tsk_your_key_here",
  agentId: "my-first-agent",
});

const interceptor = new TruseraInterceptor();
interceptor.install(client, {
  enforcement: "log",
});

// Make some API calls (automatically tracked)
await fetch("https://api.github.com/repos/Trusera/ai-bom");
await fetch("https://api.openai.com/v1/models");

// Cleanup
await client.close();
interceptor.uninstall();
```

Run it:
```bash
npx tsx demo.ts
```

## 4. View Your Events

Visit [app.trusera.io/agents](https://app.trusera.io/agents) to see:
- All HTTP calls made by your agent
- Request/response details
- Timing and performance metrics
- Policy violations (if configured)

## 5. Add Policy Enforcement

```typescript
interceptor.install(client, {
  enforcement: "block", // Blocks policy violations
  policyUrl: "https://policy.trusera.io/evaluate",
});
```

Now your agent will be blocked from making unauthorized API calls!

## Next Steps

- Read the full [README.md](README.md) for all features
- Explore [examples/](examples/) for more use cases
- Check out [LangChain.js integration](examples/langchain-integration.ts)
- Set up Cedar policies for fine-grained access control

## Common Use Cases

### Track LLM Calls

```typescript
import { EventType, createEvent } from "trusera-sdk";

client.track(createEvent(EventType.LLM_INVOKE, "openai.gpt4", {
  model: "gpt-4",
  tokens: 150,
}));
```

### Track Tool Executions

```typescript
client.track(createEvent(EventType.TOOL_CALL, "github.search", {
  query: "AI security",
  results: 42,
}));
```

### Exclude Internal URLs

```typescript
interceptor.install(client, {
  excludePatterns: [
    "^http://localhost.*",
    "^https://internal\\.company\\.com/.*",
  ],
});
```

## Troubleshooting

**Events not showing up?**
- Check your API key is correct
- Ensure `client.close()` is called (flushes remaining events)
- Enable debug mode: `new TruseraClient({ debug: true })`

**Want to see what's being tracked?**
```typescript
console.log(`Queue size: ${client.getQueueSize()}`);
```

**TypeScript errors?**
- Ensure you're using Node.js >= 18
- TypeScript >= 5.0 recommended

## Support

- Docs: [docs.trusera.io](https://docs.trusera.io)
- Issues: [github.com/Trusera/trusera-sdk-js/issues](https://github.com/Trusera/trusera-sdk-js/issues)
- Email: support@trusera.io

Happy monitoring! 🚀
