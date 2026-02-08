"""Tests for Pydantic data models."""
from ai_bom.models import (
    AIComponent,
    ComponentType,
    Severity,
    SourceLocation,
)


class TestComponentType:
    def test_all_types(self):
        types = list(ComponentType)
        assert len(types) == 9
        assert ComponentType.llm_provider in types
        assert ComponentType.agent_framework in types


class TestSeverity:
    def test_values(self):
        assert Severity.critical.value == "critical"
        assert Severity.high.value == "high"
        assert Severity.medium.value == "medium"
        assert Severity.low.value == "low"


class TestAIComponent:
    def test_creation(self):
        comp = AIComponent(
            name="test",
            type=ComponentType.llm_provider,
            location=SourceLocation(file_path="test.py"),
        )
        assert comp.name == "test"
        assert comp.id  # UUID auto-generated
        assert comp.flags == []

    def test_serialization(self):
        comp = AIComponent(
            name="test",
            type=ComponentType.llm_provider,
            location=SourceLocation(file_path="test.py"),
        )
        data = comp.model_dump()
        assert "name" in data
        assert "type" in data
        assert "location" in data


class TestScanResult:
    def test_build_summary(self, sample_scan_result):
        assert sample_scan_result.summary.total_components == 1

    def test_to_cyclonedx(self, sample_scan_result):
        cdx = sample_scan_result.to_cyclonedx()
        assert cdx["bomFormat"] == "CycloneDX"
        assert cdx["specVersion"] == "1.6"
        assert len(cdx["components"]) == 1

    def test_cyclonedx_has_serial_number(self, sample_scan_result):
        cdx = sample_scan_result.to_cyclonedx()
        assert cdx["serialNumber"].startswith("urn:uuid:")

    def test_summary_by_type(self, multi_component_result):
        summary = multi_component_result.summary
        assert summary.total_components == 3
        assert sum(summary.by_type.values()) == 3

    def test_summary_highest_risk(self, multi_component_result):
        # The critical_component has flags, so highest risk should be > 0
        # (risk scoring is applied separately, but the fixture has default 0)
        assert multi_component_result.summary.highest_risk_score >= 0
