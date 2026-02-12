# Trusera SDK Quick Start

## Installation

```bash
# Basic installation
pip install trusera-sdk

# With framework support
pip install trusera-sdk[langchain]   # For LangChain
pip install trusera-sdk[crewai]      # For CrewAI
pip install trusera-sdk[autogen]     # For AutoGen

# Development
pip install trusera-sdk[dev]
```

## 3-Line Quickstart

```python
from trusera_sdk import TruseraClient, Event, EventType

client = TruseraClient(api_key="tsk_your_key")
client.register_agent("my-agent", "custom")
client.track(Event(type=EventType.TOOL_CALL, name="search", payload={"query": "AI"}))
```

## Using the Decorator

```python
from trusera_sdk import TruseraClient, monitor, set_default_client

client = TruseraClient(api_key="tsk_your_key")
client.register_agent("my-agent", "custom")
set_default_client(client)

@monitor()  # Automatically tracks calls
def my_function(x: int) -> int:
    return x * 2

result = my_function(5)  # Tracked automatically
```

## LangChain Integration

```python
from langchain.llms import OpenAI
from trusera_sdk import TruseraClient
from trusera_sdk.integrations.langchain import TruseraCallbackHandler

client = TruseraClient(api_key="tsk_your_key")
client.register_agent("langchain-agent", "langchain")
handler = TruseraCallbackHandler(client)

llm = OpenAI(callbacks=[handler])
llm("What is AI?")  # Tracked automatically
```

## Running Examples

```bash
cd examples/

# Basic usage
python basic_usage.py

# Decorator usage
python decorator_usage.py

# LangChain integration (requires langchain-core)
python langchain_example.py
```

## Development

```bash
# Install dev dependencies
make install

# Run tests
make test

# Run linter
make lint

# Type check
make type-check

# Run all checks
make all
```

## Next Steps

- Read the full [README.md](README.md)
- Check out [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- View the [CHANGELOG.md](CHANGELOG.md) for version history
- Visit [docs.trusera.dev](https://docs.trusera.dev) for full documentation

## Support

- Issues: [GitHub Issues](https://github.com/Trusera/trusera-agent-sdk/issues)
- Email: dev@trusera.dev
- Website: [trusera.dev](https://trusera.dev)
