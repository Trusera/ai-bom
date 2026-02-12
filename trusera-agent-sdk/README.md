# Trusera Python SDK

[![PyPI version](https://badge.fury.io/py/trusera-sdk.svg)](https://badge.fury.io/py/trusera-sdk)
[![Python versions](https://img.shields.io/pypi/pyversions/trusera-sdk.svg)](https://pypi.org/project/trusera-sdk/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Python SDK for monitoring AI agents with [Trusera](https://trusera.dev). Track LLM invocations, tool calls, data access, and more to ensure your AI agents are secure and compliant.

## Installation

```bash
pip install trusera-sdk
```

### Optional Dependencies

For framework-specific integrations:

```bash
# LangChain integration
pip install trusera-sdk[langchain]

# CrewAI integration
pip install trusera-sdk[crewai]

# AutoGen integration
pip install trusera-sdk[autogen]

# Development tools
pip install trusera-sdk[dev]
```

## Quick Start

```python
from trusera_sdk import TruseraClient, Event, EventType

# Initialize the client
client = TruseraClient(api_key="tsk_your_api_key")

# Register your agent
agent_id = client.register_agent(
    name="my-agent",
    framework="custom",
    metadata={"version": "1.0.0"}
)

# Track events
client.track(Event(
    type=EventType.TOOL_CALL,
    name="web_search",
    payload={"query": "latest AI news"},
    metadata={"duration_ms": 250}
))

# Events are automatically flushed in batches
# Manual flush if needed
client.flush()

# Clean up
client.close()
```

## Using the Decorator

The `@monitor` decorator automatically tracks function calls:

```python
from trusera_sdk import TruseraClient, monitor, set_default_client, EventType

# Set up client
client = TruseraClient(api_key="tsk_your_api_key")
client.register_agent("my-agent", "custom")
set_default_client(client)

# Decorate your functions
@monitor(event_type=EventType.TOOL_CALL)
def search_database(query: str) -> list[dict]:
    # Your implementation
    return [{"id": 1, "title": "Result"}]

@monitor(event_type=EventType.LLM_INVOKE, name="gpt4_call")
async def call_llm(prompt: str) -> str:
    # Works with async functions too
    return "AI response"

# Function calls are automatically tracked
results = search_database("user query")
response = await call_llm("What is AI?")
```

## Framework Integrations

### LangChain

```python
from langchain.llms import OpenAI
from langchain.agents import initialize_agent, Tool
from trusera_sdk import TruseraClient
from trusera_sdk.integrations.langchain import TruseraCallbackHandler

# Initialize Trusera
client = TruseraClient(api_key="tsk_your_api_key")
client.register_agent("langchain-agent", "langchain")
handler = TruseraCallbackHandler(client)

# Use with LangChain
llm = OpenAI(callbacks=[handler])
agent = initialize_agent(
    tools=[...],
    llm=llm,
    callbacks=[handler]
)

# All LLM calls and tool usage are tracked
agent.run("Your query here")
```

### CrewAI

```python
from crewai import Crew, Agent, Task
from trusera_sdk import TruseraClient
from trusera_sdk.integrations.crewai import TruseraCrewCallback

# Initialize Trusera
client = TruseraClient(api_key="tsk_your_api_key")
client.register_agent("crew-agent", "crewai")
callback = TruseraCrewCallback(client)

# Create your crew
researcher = Agent(role="Researcher", goal="Research topics")
task = Task(description="Research AI trends", agent=researcher)

crew = Crew(
    agents=[researcher],
    tasks=[task],
    step_callback=callback.step_callback
)

# Execute with tracking
result = crew.kickoff()
```

### AutoGen

```python
import autogen
from trusera_sdk import TruseraClient
from trusera_sdk.integrations.autogen import TruseraAutoGenHook

# Initialize Trusera
client = TruseraClient(api_key="tsk_your_api_key")
client.register_agent("autogen-agent", "autogen")
hook = TruseraAutoGenHook(client)

# Create AutoGen agents
assistant = autogen.AssistantAgent(
    name="assistant",
    llm_config={"model": "gpt-4"}
)

# Register hook
hook.setup_agent(assistant)

# All interactions are tracked
user_proxy = autogen.UserProxyAgent(name="user")
user_proxy.initiate_chat(assistant, message="Hello")
```

## Event Types

The SDK supports tracking various types of agent activities:

- `EventType.TOOL_CALL` - Tool or function invocations
- `EventType.LLM_INVOKE` - LLM API calls
- `EventType.DATA_ACCESS` - Database queries, file reads
- `EventType.API_CALL` - External API requests
- `EventType.FILE_WRITE` - File system modifications
- `EventType.DECISION` - Agent decision points

## Configuration

### Client Options

```python
client = TruseraClient(
    api_key="tsk_your_api_key",
    base_url="https://api.trusera.dev",  # Optional, defaults to production
    flush_interval=5.0,                    # Seconds between auto-flushes
    batch_size=100,                        # Events per batch
    timeout=10.0                           # HTTP request timeout
)
```

### Context Manager

Use the client as a context manager for automatic cleanup:

```python
with TruseraClient(api_key="tsk_your_api_key") as client:
    client.register_agent("my-agent", "custom")
    # ... track events ...
# Automatically flushed and closed
```

## Best Practices

1. **Use Context Manager**: Ensures events are flushed on exit
2. **Set Agent ID Early**: Call `register_agent()` or `set_agent_id()` before tracking
3. **Batch Operations**: Let the SDK handle batching automatically
4. **Sensitive Data**: Use `capture_args=False` in `@monitor` for sensitive functions
5. **Error Handling**: The SDK logs errors but won't crash your application

## Environment Variables

```bash
# Optional: Set default API key
export TRUSERA_API_KEY=tsk_your_api_key

# Optional: Custom API endpoint
export TRUSERA_API_URL=https://api.trusera.dev
```

## Development

```bash
# Clone the repository
git clone https://github.com/Trusera/trusera-agent-sdk.git
cd trusera-agent-sdk

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Type checking
mypy trusera_sdk
```

## Documentation

Full documentation is available at [docs.trusera.dev/sdk/python](https://docs.trusera.dev/sdk/python)

## Support

- Website: [trusera.dev](https://trusera.dev)
- Documentation: [docs.trusera.dev](https://docs.trusera.dev)
- Issues: [GitHub Issues](https://github.com/Trusera/trusera-agent-sdk/issues)
- Email: dev@trusera.dev

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

---

Built with care by the Trusera team. Making AI agents secure and trustworthy.
