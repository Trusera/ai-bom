# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial SDK implementation
- Client for tracking agent events
- HTTP interceptor for monitoring outbound requests
- Three enforcement modes: log, warn, block
- Event types: tool_call, llm_invoke, data_access, api_call, file_write, decision
- Background event flushing with configurable interval
- Batch processing for efficient event submission
- Thread-safe concurrent request handling
- Header sanitization for sensitive data
- Pattern-based URL exclusion and blocking
- Agent registration API
- Comprehensive test suite with 85%+ coverage
- Example programs demonstrating key features
- CI/CD pipeline with GitHub Actions
- golangci-lint configuration
- Documentation and contributing guidelines

### Features
- Zero external dependencies (stdlib only)
- Builder pattern for event creation
- Functional options for client configuration
- Request/response body capture with size limits
- Multiple enforcement modes for flexible policy application
- Automatic retry and error handling

## [0.1.0] - 2026-02-13

### Added
- First pre-release version
- Core functionality for agent monitoring
- HTTP interception capabilities
- Basic documentation and examples
