# Changelog

All notable changes to the Trusera Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-13

### Added
- Initial release of the Trusera Python SDK
- Core `TruseraClient` for event tracking and API communication
- Event types: `TOOL_CALL`, `LLM_INVOKE`, `DATA_ACCESS`, `API_CALL`, `FILE_WRITE`, `DECISION`
- `@monitor` decorator for automatic function tracking
- Support for both sync and async functions
- Automatic batching and background flushing
- Context manager support for clean resource management
- LangChain integration with `TruseraCallbackHandler`
- CrewAI integration with `TruseraCrewCallback`
- AutoGen integration with `TruseraAutoGenHook`
- Comprehensive test suite with >90% coverage
- Type hints throughout the codebase
- Apache 2.0 license

### Framework Support
- LangChain Core >=0.1.0
- CrewAI >=0.1.0
- AutoGen >=0.2.0

### Development Tools
- pytest for testing
- pytest-asyncio for async test support
- ruff for linting
- mypy for type checking
- GitHub Actions for CI/CD

[0.1.0]: https://github.com/Trusera/trusera-agent-sdk/releases/tag/v0.1.0
