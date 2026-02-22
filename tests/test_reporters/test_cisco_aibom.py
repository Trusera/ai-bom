"""Tests for Cisco AIBOM reporter."""

import json

from ai_bom.models import AIComponent, ComponentType, ScanResult, SourceLocation, UsageType
from ai_bom.reporters import get_reporter
from ai_bom.reporters.cisco_aibom import CiscoAIBOMReporter


def test_cisco_aibom_render_has_required_sections() -> None:
    component = AIComponent(
        name="openai",
        type=ComponentType.llm_provider,
        provider="OpenAI",
        location=SourceLocation(file_path="app.py", line_number=1),
        usage_type=UsageType.completion,
        source="code",
    )
    result = ScanResult(target_path="/test")
    result.components = [component]
    result.build_summary()

    reporter = CiscoAIBOMReporter()
    output = reporter.render(result)
    data = json.loads(output)

    assert "aibom_analysis" in data
    analysis = data["aibom_analysis"]
    assert "metadata" in analysis
    assert "sources" in analysis
    assert "components" in analysis["sources"]
    assert "summary" in analysis


def test_get_reporter_cisco_aibom_format() -> None:
    reporter = get_reporter("cisco-aibom")
    assert isinstance(reporter, CiscoAIBOMReporter)
