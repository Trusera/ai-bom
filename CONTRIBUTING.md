# Contributing to AI-BOM

Thanks for your interest in contributing to AI-BOM! This guide covers the basics.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Trusera/ai-bom.git
cd ai-bom

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting. Check your code before submitting:

```bash
ruff check src/ tests/
```

The enforced rule sets are: E (pycodestyle errors), F (pyflakes), I (isort), W (pycodestyle warnings).

## Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest -v --cov=ai_bom --cov-report=term-missing

# Run a specific test file
pytest tests/test_cli.py -v
```

All 124 tests must pass before submitting a PR.

## Project Structure

```
src/ai_bom/
  cli.py          # CLI entry point
  config.py       # Detection patterns and configuration
  scanners/       # Scanner implementations (code, docker, cloud, etc.)
  detectors/      # Pattern detection engines
  reporters/      # Output formatters (SARIF, CycloneDX, HTML, etc.)
  utils/          # Risk scoring and helpers
tests/            # Mirror of src/ structure
```

## Adding a New Scanner

1. Create a new file in `src/ai_bom/scanners/`
2. Subclass `BaseScanner` — auto-registration happens via `__init_subclass__`
3. Add detection patterns to `config.py`
4. Add tests in `tests/test_scanners/`

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Ensure `ruff check src/ tests/` passes with 0 errors
4. Ensure `pytest -v` passes all tests
5. Submit a PR with a clear description of the change
6. CI will run lint + tests on Python 3.10–3.13

## Reporting Issues

Use [GitHub Issues](https://github.com/Trusera/ai-bom/issues) with the provided templates.
