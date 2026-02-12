# Contributing to trusera-sdk-go

Thank you for your interest in contributing to the Trusera Go SDK!

## Development Setup

### Prerequisites

- Go 1.21 or higher
- Git

### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/trusera-sdk-go.git
   cd trusera-sdk-go
   ```

3. Install dependencies:
   ```bash
   go mod download
   ```

4. Run tests:
   ```bash
   go test -v ./...
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Run tests with race detection
go test -race ./...

# Run specific test
go test -run TestName ./...
```

### Code Quality

We use `golangci-lint` for linting. Install it:

```bash
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

Run linting:

```bash
golangci-lint run
```

### Code Style

- Follow standard Go conventions and idioms
- Use `gofmt` to format code (automatically done by most editors)
- Write clear, concise comments for exported functions
- Keep functions focused and small
- Prefer composition over complexity

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `test/description` - Test additions or improvements

### Commit Messages

Follow conventional commits format:

```
type(scope): brief description

Detailed explanation if needed.

Fixes #issue-number
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Build process or auxiliary tool changes

Examples:
```
feat(interceptor): add request timeout enforcement

fix(client): prevent race condition in event queue

docs(readme): add examples for block mode
```

### Pull Request Process

1. Update tests for any new functionality
2. Ensure all tests pass: `go test ./...`
3. Run linting: `golangci-lint run`
4. Update documentation if needed
5. Update CHANGELOG.md with your changes
6. Create a pull request with a clear description

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How have you tested this?

## Checklist
- [ ] Tests pass
- [ ] Linting passes
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

## Project Structure

```
trusera-sdk-go/
├── trusera.go           # Main client implementation
├── events.go            # Event types and creation
├── interceptor.go       # HTTP interception logic
├── *_test.go            # Test files
├── examples/            # Example programs
│   ├── basic/
│   ├── http-interceptor/
│   └── block-mode/
├── .github/
│   └── workflows/
│       └── ci.yml       # CI/CD configuration
└── README.md
```

## Testing Guidelines

### Writing Tests

- Use table-driven tests where appropriate
- Test both success and failure cases
- Use `httptest` for HTTP-related tests
- Ensure thread safety in concurrent tests
- Mock external dependencies

Example:

```go
func TestFeature(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    string
        wantErr bool
    }{
        {"valid input", "test", "result", false},
        {"invalid input", "", "", true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := Feature(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if got != tt.want {
                t.Errorf("got %v, want %v", got, tt.want)
            }
        })
    }
}
```

### Test Coverage

- Maintain at least 80% test coverage
- Critical paths should have 100% coverage
- Test edge cases and error conditions

## Documentation

### Code Comments

- All exported functions, types, and constants must have comments
- Comments should explain "why", not just "what"
- Use complete sentences with proper punctuation

Example:

```go
// Client sends agent events to Trusera API for monitoring and compliance.
// It handles batching, retries, and background flushing automatically.
type Client struct {
    // ...
}

// NewClient creates a Trusera monitoring client with the given API key.
// Use functional options to customize behavior.
func NewClient(apiKey string, opts ...Option) *Client {
    // ...
}
```

### README Updates

Update README.md when:
- Adding new features
- Changing API behavior
- Adding new configuration options

## Release Process

1. Update version in relevant files
2. Update CHANGELOG.md with release notes
3. Create git tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. GitHub Actions will handle the release

## Dependencies

This SDK uses **only the Go standard library**. Adding external dependencies requires strong justification and discussion in an issue first.

## Questions?

- Open an issue for bugs or feature requests
- Join our [Discord community](https://discord.gg/trusera)
- Email: opensource@trusera.io

## Code of Conduct

Be respectful, inclusive, and professional. See [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
