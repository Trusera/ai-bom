"""Shared test fixtures for AI-BOM test suite."""
from pathlib import Path

import pytest

from ai_bom.models import (
    AIComponent,
    ComponentType,
    N8nWorkflowInfo,
    ScanResult,
    SourceLocation,
    UsageType,
)


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_component():
    """A basic AI component for testing."""
    return AIComponent(
        name="openai",
        type=ComponentType.llm_provider,
        provider="OpenAI",
        model_name="gpt-4o",
        location=SourceLocation(
            file_path="app.py",
            line_number=5,
            context_snippet="from openai import OpenAI",
        ),
        usage_type=UsageType.completion,
        source="code",
    )


@pytest.fixture
def critical_component():
    """A high-risk AI component with multiple flags."""
    return AIComponent(
        name="openai",
        type=ComponentType.llm_provider,
        provider="OpenAI",
        model_name="gpt-3.5-turbo",
        location=SourceLocation(file_path="app.py", line_number=10),
        usage_type=UsageType.completion,
        flags=["hardcoded_api_key", "deprecated_model", "internet_facing", "no_auth"],
        source="code",
    )


@pytest.fixture
def n8n_component():
    """An n8n workflow AI component."""
    return AIComponent(
        name="AI Agent",
        type=ComponentType.agent_framework,
        provider="OpenAI",
        location=SourceLocation(file_path="workflows/support.json"),
        usage_type=UsageType.agent,
        flags=["webhook_no_auth", "mcp_unknown_server"],
        source="n8n",
    )


@pytest.fixture
def sample_scan_result(sample_component):
    """A scan result with one component."""
    result = ScanResult(target_path="/test/path")
    result.components = [sample_component]
    result.build_summary()
    return result


@pytest.fixture
def multi_component_result(sample_component, critical_component, n8n_component):
    """A scan result with multiple components."""
    result = ScanResult(target_path="/test/path")
    result.components = [sample_component, critical_component, n8n_component]
    result.n8n_workflows = [
        N8nWorkflowInfo(
            workflow_name="Support Agent",
            workflow_id="wf-001",
            nodes=["agent", "lmChatOpenAi", "mcpClientTool"],
            trigger_type="webhook",
        )
    ]
    result.build_summary()
    return result


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with test files."""
    # Python file with OpenAI usage
    app_py = tmp_path / "app.py"
    app_py.write_text(
        'from openai import OpenAI\n'
        'client = OpenAI(api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz1234")\n'
        'response = client.chat.completions.create(model="gpt-3.5-turbo", messages=[])\n'
    )

    # Requirements file
    req = tmp_path / "requirements.txt"
    req.write_text("openai>=1.0.0\nfastapi>=0.100.0\n")

    # .env file
    env = tmp_path / ".env.example"
    env.write_text(
        'OPENAI_API_KEY=sk-demo1234567890abcdefghijklmnopqrstuvwxyz0000\n'
        'ANTHROPIC_API_KEY=sk-ant-demo1234567890abcdefghij\n'
    )

    return tmp_path
