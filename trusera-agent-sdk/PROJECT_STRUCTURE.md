# Trusera Agent SDK - Project Structure

This document describes the complete structure and architecture of the Trusera Python SDK.

## Directory Structure

```
trusera-agent-sdk/
├── trusera_sdk/                    # Main package
│   ├── __init__.py                 # Package exports
│   ├── client.py                   # TruseraClient (215 lines)
│   ├── events.py                   # Event types and structures (63 lines)
│   ├── decorators.py               # @monitor decorator (220 lines)
│   └── integrations/               # Framework integrations
│       ├── __init__.py
│       ├── langchain.py            # LangChain integration (258 lines)
│       ├── crewai.py               # CrewAI integration (168 lines)
│       └── autogen.py              # AutoGen integration (187 lines)
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures (50 lines)
│   ├── test_client.py              # Client tests (207 lines)
│   ├── test_events.py              # Event tests (101 lines)
│   ├── test_decorators.py          # Decorator tests (198 lines)
│   └── test_langchain.py           # LangChain tests (158 lines)
├── examples/                       # Usage examples
│   ├── basic_usage.py              # Basic SDK usage
│   ├── decorator_usage.py          # Decorator examples
│   └── langchain_example.py        # LangChain integration
├── .github/workflows/              # CI/CD
│   ├── test.yml                    # Test workflow
│   └── publish.yml                 # PyPI publish workflow
├── pyproject.toml                  # Project metadata & dependencies
├── README.md                       # Main documentation (266 lines)
├── QUICKSTART.md                   # Quick start guide
├── LICENSE                         # Apache 2.0 license
├── CONTRIBUTING.md                 # Contribution guidelines
├── CHANGELOG.md                    # Version history
├── Makefile                        # Development commands
├── MANIFEST.in                     # Package manifest
├── .gitignore                      # Git ignore rules
├── .ruff.toml                      # Ruff linter config
└── py.typed                        # Type hints marker
```

## Core Components

### 1. TruseraClient (`client.py`)

**Purpose**: Main client for interacting with the Trusera API.

**Key Features**:
- Asynchronous event batching with background flush thread
- Thread-safe queue for concurrent event tracking
- Context manager support (`with` statement)
- Automatic cleanup via `atexit`
- HTTP communication with `httpx`

**Main Methods**:
- `__init__(api_key, base_url, flush_interval, batch_size)` - Initialize client
- `register_agent(name, framework, metadata)` - Register new agent
- `track(event)` - Queue event for sending
- `flush()` - Immediately send queued events
- `close()` - Clean shutdown with final flush

**Architecture**:
```
Queue (thread-safe) → Background Thread → Batch HTTP POST → Trusera API
                         (every N seconds)
```

### 2. Event System (`events.py`)

**Event Types**:
- `TOOL_CALL` - Tool/function invocations
- `LLM_INVOKE` - LLM API calls
- `DATA_ACCESS` - Database queries, file reads
- `API_CALL` - External API requests
- `FILE_WRITE` - File system modifications
- `DECISION` - Agent decision points

**Event Structure**:
```python
{
    "id": "uuid",
    "type": "tool_call",
    "name": "web_search",
    "payload": {...},      # Event-specific data
    "metadata": {...},     # Context (duration, etc.)
    "timestamp": "ISO8601"
}
```

### 3. Monitor Decorator (`decorators.py`)

**Purpose**: Automatic function tracking without manual event creation.

**Features**:
- Works with sync and async functions
- Captures arguments, return values, exceptions
- Measures execution duration
- Configurable capture options
- Type-preserving (maintains function signatures)

**Usage**:
```python
@monitor(
    event_type=EventType.TOOL_CALL,
    name="custom_name",
    capture_args=True,
    capture_result=True
)
def my_function(x: int) -> int:
    return x * 2
```

### 4. Framework Integrations

#### LangChain (`integrations/langchain.py`)

**Integration**: `TruseraCallbackHandler(BaseCallbackHandler)`

**Captures**:
- `on_llm_start/end` → LLM_INVOKE events
- `on_tool_start/end/error` → TOOL_CALL events
- `on_chain_start/end` → DECISION events

**Usage**:
```python
handler = TruseraCallbackHandler(client)
llm = OpenAI(callbacks=[handler])
```

#### CrewAI (`integrations/crewai.py`)

**Integration**: `TruseraCrewCallback`

**Captures**:
- Task execution → DECISION events
- Agent actions → TOOL_CALL events
- Step outputs → tracked continuously

**Usage**:
```python
callback = TruseraCrewCallback(client)
crew = Crew(agents=[...], tasks=[...], step_callback=callback.step_callback)
```

#### AutoGen (`integrations/autogen.py`)

**Integration**: `TruseraAutoGenHook`

**Captures**:
- Message exchanges → DECISION events
- Function calls → TOOL_CALL events
- Agent interactions → tracked via hooks

**Usage**:
```python
hook = TruseraAutoGenHook(client)
hook.setup_agent(assistant)
```

## Testing Strategy

### Test Coverage

- **Unit Tests**: Core functionality (client, events, decorators)
- **Integration Tests**: Framework integrations (LangChain, etc.)
- **Mock Strategy**: HTTP calls mocked via `httpx.Client` patches
- **Async Tests**: `pytest-asyncio` for async function testing

### Key Test Files

1. `test_client.py` - Client initialization, tracking, flushing, batching
2. `test_events.py` - Event creation, serialization, enum values
3. `test_decorators.py` - Sync/async decoration, error handling
4. `test_langchain.py` - Callback handler behavior

### Running Tests

```bash
pytest                              # Run all tests
pytest -v                           # Verbose output
pytest --cov=trusera_sdk           # With coverage
pytest tests/test_client.py        # Specific file
```

## Development Workflow

### Setup

```bash
git clone https://github.com/Trusera/trusera-agent-sdk.git
cd trusera-agent-sdk
make install  # or: pip install -e ".[dev]"
```

### Code Quality

```bash
make lint           # Run ruff linter
make lint-fix       # Auto-fix issues
make type-check     # Run mypy
make test           # Run pytest
make all            # Lint + type-check + test
```

### Building & Publishing

```bash
make build          # Build wheel + sdist
make publish        # Upload to PyPI
```

### CI/CD Pipeline

**On Push/PR** (`.github/workflows/test.yml`):
- Test on Python 3.9, 3.10, 3.11, 3.12
- Run pytest with all integrations
- Run linter (ruff)
- Run type checker (mypy)

**On Tag** (`.github/workflows/publish.yml`):
- Build package
- Publish to PyPI
- Uses trusted publishing (OIDC)

## Dependencies

### Core

- `httpx>=0.24.0` - HTTP client (async-capable, modern)

### Optional

- `langchain-core>=0.1.0` - LangChain integration
- `crewai>=0.1.0` - CrewAI integration
- `pyautogen>=0.2.0` - AutoGen integration

### Development

- `pytest>=7.0` - Testing framework
- `pytest-asyncio>=0.21` - Async test support
- `ruff>=0.1.0` - Linter and formatter
- `mypy>=1.0` - Static type checker

## Design Principles

1. **Zero Config by Default**: Works out of the box with sensible defaults
2. **Thread-Safe**: Queue and client operations are thread-safe
3. **Non-Blocking**: Background thread handles I/O, main thread unaffected
4. **Graceful Degradation**: Logs errors but doesn't crash application
5. **Type-Safe**: Full type hints for IDE support and static analysis
6. **Pythonic**: Follows PEP 8, uses context managers, decorators
7. **Testable**: High test coverage with comprehensive fixtures

## API Endpoints

The SDK communicates with these Trusera API endpoints:

- `POST /api/v1/agents` - Register new agent
- `POST /api/v1/agents/{agent_id}/events` - Send event batch

**Request Format**:
```json
{
  "events": [
    {
      "id": "uuid",
      "type": "tool_call",
      "name": "search",
      "payload": {...},
      "metadata": {...},
      "timestamp": "2026-02-13T12:00:00Z"
    }
  ]
}
```

## Performance Characteristics

- **Queue**: O(1) enqueue/dequeue (Python `queue.Queue`)
- **Memory**: Events held in memory until flushed (configurable batch size)
- **Network**: Batched HTTP requests (default: 100 events or 5 seconds)
- **Threading**: Single background thread for all flush operations
- **Overhead**: Minimal (microseconds per event tracked)

## Security Considerations

1. **API Keys**: Prefix validation (`tsk_`), stored in memory only
2. **HTTPS**: All API communication over TLS
3. **Sensitive Data**: `@monitor(capture_args=False)` to exclude secrets
4. **No Telemetry**: SDK doesn't collect or send usage data

## Future Enhancements

Potential additions for future versions:

- Async client (`AsyncTruseraClient`)
- Streaming events (WebSocket support)
- Local event storage (disk buffer)
- More framework integrations (Llama Index, Haystack)
- Event sampling/filtering
- Structured logging integration
- OpenTelemetry compatibility

## Version History

- **v0.1.0** (2026-02-13) - Initial release

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## License

Apache License 2.0 - See [LICENSE](LICENSE) file.

## Contact

- Website: https://trusera.dev
- Email: dev@trusera.dev
- GitHub: https://github.com/Trusera/trusera-agent-sdk
- Documentation: https://docs.trusera.dev/sdk/python
