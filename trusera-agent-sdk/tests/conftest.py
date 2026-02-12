"""Shared fixtures for tests."""

import pytest
from unittest.mock import Mock, MagicMock
import httpx

from trusera_sdk import TruseraClient


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Mock httpx.Client for testing."""
    mock_client = Mock(spec=httpx.Client)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "agent_123"}
    mock_response.raise_for_status = Mock()

    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.close = Mock()

    # Patch httpx.Client constructor
    monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

    return mock_client


@pytest.fixture
def trusera_client(mock_httpx_client):
    """Create a TruseraClient instance with mocked HTTP."""
    client = TruseraClient(
        api_key="tsk_test_key",
        base_url="https://api.test.trusera.dev",
        flush_interval=0.1,  # Fast for testing
        batch_size=5,
    )
    client.set_agent_id("agent_test_123")
    yield client
    client.close()


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "ok"}
    response.raise_for_status = Mock()
    return response
