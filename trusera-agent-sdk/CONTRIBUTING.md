# Contributing to Trusera SDK

Thank you for your interest in contributing to the Trusera Python SDK! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/trusera-agent-sdk.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `pytest`
6. Commit your changes: `git commit -m "Add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a Pull Request

## Development Setup

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev,langchain,crewai,autogen]"
```

## Code Standards

### Style Guide

We follow PEP 8 and use several tools to enforce code quality:

```bash
# Run linter
ruff check .

# Auto-fix issues
ruff check --fix .

# Type checking
mypy trusera_sdk

# Format code (if using black)
black trusera_sdk tests
```

### Type Hints

All functions should have type hints:

```python
def my_function(arg1: str, arg2: int) -> dict[str, Any]:
    """Function with type hints."""
    return {"result": arg1 * arg2}
```

### Docstrings

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int) -> str:
    """
    Brief description of the function.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When something goes wrong
    """
    pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_client.py

# Run with coverage
pytest --cov=trusera_sdk --cov-report=html
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names
- Aim for high test coverage (>90%)

Example test:

```python
def test_my_feature(trusera_client):
    """Test my new feature."""
    result = trusera_client.my_feature()
    assert result is not None
    assert result["status"] == "success"
```

## Pull Request Process

1. **Update Tests**: Add or update tests for your changes
2. **Update Documentation**: Update README.md or docstrings as needed
3. **Run All Tests**: Ensure all tests pass
4. **Check Code Quality**: Run linter and type checker
5. **Write Clear Commit Messages**: Use descriptive commit messages
6. **Update Changelog**: Add a note about your changes
7. **Submit PR**: Open a pull request with a clear description

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
How has this been tested?

## Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Changelog updated
```

## Adding Framework Integrations

To add support for a new AI framework:

1. Create `trusera_sdk/integrations/your_framework.py`
2. Implement the integration following existing patterns
3. Add tests in `tests/test_your_framework.py`
4. Add to `pyproject.toml` optional dependencies
5. Update README.md with usage example

## Reporting Bugs

Open an issue with:
- Clear title
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (Python version, OS, SDK version)
- Code sample if possible

## Feature Requests

Open an issue with:
- Clear description of the feature
- Use case / motivation
- Example API if proposing new functionality

## Questions

For questions about using the SDK:
- Check the [documentation](https://docs.trusera.dev)
- Search existing issues
- Open a new issue with the "question" label

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## Code of Conduct

Be respectful and constructive in all interactions.

Thank you for contributing to Trusera!
