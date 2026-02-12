# Trusera SDK Examples

This directory contains runnable examples demonstrating key features of the Trusera SDK.

## Running Examples

All examples use TypeScript and can be run with `tsx`:

```bash
# Install dependencies first
npm install

# Run an example
npx tsx examples/basic-usage.ts
```

## Examples

### 1. basic-usage.ts

**What it demonstrates**:
- Creating a TruseraClient
- Installing the HTTP interceptor
- Automatic tracking of fetch calls
- Manual event tracking
- Queue management and flushing

**Run it**:
```bash
npx tsx examples/basic-usage.ts
```

**Expected output**:
```
✓ Trusera client initialized
✓ HTTP interceptor installed
--- Making HTTP requests (auto-tracked) ---
✓ GitHub API: ai-bom - 42 stars
✓ Todo API: delectus aut autem
--- Tracking custom events ---
✓ Tracked TOOL_CALL event
✓ Tracked LLM_INVOKE event
✓ Tracked DATA_ACCESS event
...
```

### 2. langchain-integration.ts

**What it demonstrates**:
- TruseraLangChainHandler callback integration
- Automatic LLM call tracking
- Tool execution tracking
- Chain step tracking
- Agent registration

**Prerequisites**:
```bash
npm install langchain
```

**Run it**:
```bash
npx tsx examples/langchain-integration.ts
```

**Note**: The main integration code is commented out to avoid requiring langchain as a dependency. Uncomment the code blocks to see the full integration.

### 3. policy-enforcement.ts

**What it demonstrates**:
- All three enforcement modes: log, warn, block
- Policy-based request blocking
- Exclude patterns for selective interception
- Multiple client instances

**Run it**:
```bash
npx tsx examples/policy-enforcement.ts
```

**Expected output**:
```
==============================================
Trusera SDK - Policy Enforcement Examples
==============================================

=== LOG MODE (silent tracking) ===
✓ Request completed (log mode - all allowed)

=== WARN MODE (warnings in console) ===
[Trusera] Policy violation (allowed): Unauthorized API access
✓ Request completed (warn mode - allowed with warning)

=== BLOCK MODE (strict enforcement) ===
✗ Request blocked: [Trusera] Policy violation: Unauthorized API access

=== EXCLUDE PATTERNS (selective interception) ===
✓ localhost request (not tracked)
✓ GitHub API request (tracked)
Events tracked: 1
```

## Environment Variables

Set your API key before running examples:

```bash
export TRUSERA_API_KEY="tsk_your_api_key_here"
```

Or create a `.env` file in the examples directory:

```bash
TRUSERA_API_KEY=tsk_your_api_key_here
```

## Troubleshooting

**"Cannot find module 'trusera-sdk'"**
- Run `npm run build` to compile the TypeScript source
- Or install the package: `npm install trusera-sdk`

**"Invalid API key format"**
- Ensure your API key starts with `tsk_`
- Get a key from [app.trusera.io](https://app.trusera.io)

**"Events not showing up in dashboard"**
- Verify your API key is correct
- Check that `client.close()` is called (flushes events)
- Enable debug mode: `new TruseraClient({ debug: true })`

## Creating Your Own Example

```typescript
import { TruseraClient, TruseraInterceptor } from "trusera-sdk";

async function myExample() {
  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY!,
    debug: true,
  });

  const interceptor = new TruseraInterceptor();
  interceptor.install(client);

  // Your code here
  await fetch("https://api.example.com/data");

  await client.close();
  interceptor.uninstall();
}

myExample().catch(console.error);
```

## Next Steps

- Read the [full README](../README.md) for complete API documentation
- Check out the [Quick Start Guide](../QUICKSTART.md)
- Explore the [source code](../src/) for implementation details

## Support

Questions about these examples? Open an issue on [GitHub](https://github.com/Trusera/trusera-sdk-js/issues).
