#!/bin/bash

# Development setup script for Trusera SDK

set -e

echo "=== Trusera SDK Development Setup ==="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

REQUIRED_VERSION="3.9"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "Error: Python 3.9+ required"
    exit 1
fi

echo "✓ Python version OK"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"
echo ""

# Install package in development mode
echo "Installing trusera-sdk in development mode..."
pip install -e ".[dev,langchain,crewai,autogen]" > /dev/null 2>&1
echo "✓ Package installed"
echo ""

# Run tests
echo "Running tests..."
pytest -v --tb=short
echo ""

# Run linter
echo "Running linter..."
ruff check .
echo "✓ Linting passed"
echo ""

# Run type checker
echo "Running type checker..."
mypy trusera_sdk
echo "✓ Type checking passed"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "Virtual environment is activated. To deactivate, run: deactivate"
echo ""
echo "Available commands:"
echo "  make test       - Run tests"
echo "  make lint       - Run linter"
echo "  make type-check - Run type checker"
echo "  make all        - Run all checks"
echo "  make build      - Build package"
echo ""
echo "To activate the venv in the future:"
echo "  source venv/bin/activate"
