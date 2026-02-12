.PHONY: install test lint type-check format clean build publish

install:
	pip install -e ".[dev,langchain,crewai,autogen]"

test:
	pytest -v --tb=short --cov=trusera_sdk --cov-report=html --cov-report=term

lint:
	ruff check .

lint-fix:
	ruff check --fix .

type-check:
	mypy trusera_sdk

format:
	ruff format .

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

publish: build
	python -m twine upload dist/*

dev:
	pip install -e ".[dev]"

all: lint type-check test
