"""Tests for validating CycloneDX and SARIF output schemas.

This test suite ensures that the reporters generate valid output conforming to
their respective JSON schema specifications.
"""

import json

import pytest

from ai_bom.models import (
    AIComponent,
    ComponentType,
    RiskAssessment,
    ScanResult,
    Severity,
    SourceLocation,
    UsageType,
)
from ai_bom.reporters.cyclonedx import CycloneDXReporter
from ai_bom.reporters.sarif import SARIFReporter

try:
    from jsonschema import Draft7Validator

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


# CycloneDX 1.6 schema snippet (key required fields only)
CYCLONEDX_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["bomFormat", "specVersion", "version", "components"],
    "properties": {
        "bomFormat": {"type": "string", "enum": ["CycloneDX"]},
        "specVersion": {"type": "string", "pattern": "^1\\.6$"},
        "version": {"type": "integer", "minimum": 1},
        "serialNumber": {"type": "string", "pattern": "^urn:uuid:"},
        "metadata": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string"},
                "tools": {"type": "object"},
            },
        },
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "name", "bom-ref"],
                "properties": {
                    "bom-ref": {"type": "string"},
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "description": {"type": "string"},
                    "properties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "value"],
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}

# SARIF 2.1.0 schema snippet (key required fields only)
SARIF_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "runs"],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"type": "string", "enum": ["2.1.0"]},
        "runs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["tool", "results"],
                "properties": {
                    "tool": {
                        "type": "object",
                        "required": ["driver"],
                        "properties": {
                            "driver": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "organization": {"type": "string"},
                                    "version": {"type": "string"},
                                    "informationUri": {"type": "string"},
                                    "rules": {"type": "array"},
                                },
                            }
                        },
                    },
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["ruleId", "message", "level"],
                            "properties": {
                                "ruleId": {"type": "string"},
                                "ruleIndex": {"type": "integer"},
                                "level": {
                                    "type": "string",
                                    "enum": ["none", "note", "warning", "error"],
                                },
                                "message": {
                                    "type": "object",
                                    "required": ["text"],
                                    "properties": {"text": {"type": "string"}},
                                },
                                "locations": {"type": "array"},
                                "properties": {"type": "object"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def _make_component(**kwargs):
    """Helper to create AIComponent with defaults."""
    defaults = {
        "name": "test-component",
        "type": ComponentType.llm_provider,
        "location": SourceLocation(file_path="test.py", line_number=10),
    }
    defaults.update(kwargs)
    return AIComponent(**defaults)


class TestCycloneDXSchemaValidation:
    """Tests for CycloneDX output schema validation."""

    def test_cyclonedx_valid_json_output(self, sample_scan_result):
        """Test that CycloneDX reporter produces valid JSON."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)

        # Should parse as JSON
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_cyclonedx_required_fields(self, sample_scan_result):
        """Test that CycloneDX output has all required top-level fields."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        # Required fields per CycloneDX 1.6 spec
        assert "bomFormat" in parsed
        assert "specVersion" in parsed
        assert "version" in parsed
        assert "components" in parsed

        # Verify values
        assert parsed["bomFormat"] == "CycloneDX"
        assert parsed["specVersion"] == "1.6"
        assert isinstance(parsed["version"], int)
        assert parsed["version"] >= 1
        assert isinstance(parsed["components"], list)

    def test_cyclonedx_serial_number_format(self, sample_scan_result):
        """Test that serialNumber follows URN UUID format."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        assert "serialNumber" in parsed
        assert parsed["serialNumber"].startswith("urn:uuid:")
        # UUID format check (basic)
        uuid_part = parsed["serialNumber"].replace("urn:uuid:", "")
        assert len(uuid_part) == 36  # Standard UUID length with hyphens

    def test_cyclonedx_metadata_structure(self, sample_scan_result):
        """Test that metadata section has expected structure."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        assert "metadata" in parsed
        metadata = parsed["metadata"]

        assert "timestamp" in metadata
        assert "tools" in metadata
        assert isinstance(metadata["tools"], dict)

    def test_cyclonedx_component_required_fields(self, sample_scan_result):
        """Test that each component has required fields."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        components = parsed["components"]
        assert len(components) >= 1

        for component in components:
            # Required per CycloneDX spec
            assert "type" in component
            assert "name" in component
            assert "bom-ref" in component
            assert isinstance(component["type"], str)
            assert isinstance(component["name"], str)
            assert isinstance(component["bom-ref"], str)

    def test_cyclonedx_component_properties(self, sample_scan_result):
        """Test that component properties are structured correctly."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        components = parsed["components"]
        for component in components:
            if "properties" in component:
                properties = component["properties"]
                assert isinstance(properties, list)
                for prop in properties:
                    assert "name" in prop
                    assert "value" in prop
                    assert isinstance(prop["name"], str)
                    assert isinstance(prop["value"], str)

    def test_cyclonedx_schema_validation(self, multi_component_result):
        """Test that output validates against CycloneDX schema."""
        from ai_bom.utils.validator import get_schema
        reporter = CycloneDXReporter()
        output = reporter.render(multi_component_result)
        parsed = json.loads(output)

        # Validate against schema
        schema = get_schema()
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(parsed))
        assert len(errors) == 0, f"Schema validation errors: {errors}"

    def test_cyclonedx_empty_components(self):
        """Test that empty component list produces valid output."""
        result = ScanResult(target_path="/test/path")
        result.build_summary()

        reporter = CycloneDXReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        assert parsed["bomFormat"] == "CycloneDX"
        assert parsed["components"] == []
        assert isinstance(parsed["components"], list)

    def test_cyclonedx_special_characters_in_names(self):
        """Test that special characters in component names don't break output."""
        component = _make_component(
            name="test/component<>&\"quotes'",
            provider="Provider & Co.",
            model_name="model-v1.0-beta",
        )
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = CycloneDXReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        assert len(parsed["components"]) == 1
        assert "test/component<>&\"quotes'" in parsed["components"][0]["name"]

    def test_cyclonedx_very_long_component_name(self):
        """Test that very long component names are handled."""
        long_name = "a" * 1000
        component = _make_component(name=long_name)
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = CycloneDXReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        assert parsed["components"][0]["name"] == long_name

    def test_cyclonedx_type_mapping(self):
        """Test that ComponentType is correctly mapped to CycloneDX types."""
        test_cases = [
            (ComponentType.llm_provider, "machine-learning-model"),
            (ComponentType.agent_framework, "framework"),
            (ComponentType.model, "machine-learning-model"),
            (ComponentType.endpoint, "service"),
            (ComponentType.container, "container"),
            (ComponentType.tool, "library"),
            (ComponentType.mcp_server, "service"),
            (ComponentType.mcp_client, "library"),
            (ComponentType.workflow, "framework"),
        ]

        for comp_type, expected_cdx_type in test_cases:
            component = _make_component(type=comp_type)
            result = ScanResult(target_path="/test/path")
            result.components = [component]
            result.build_summary()

            reporter = CycloneDXReporter()
            output = reporter.render(result)
            parsed = json.loads(output)

            assert parsed["components"][0]["type"] == expected_cdx_type

    def test_cyclonedx_trusera_properties(self, critical_component):
        """Test that Trusera-specific properties are included."""
        result = ScanResult(target_path="/test/path")
        result.components = [critical_component]
        result.build_summary()

        reporter = CycloneDXReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        properties = parsed["components"][0]["properties"]
        prop_names = [p["name"] for p in properties]

        # Check for expected Trusera properties
        assert "trusera:risk_score" in prop_names
        assert "trusera:usage_type" in prop_names
        assert "trusera:source_location" in prop_names
        assert "trusera:provider" in prop_names
        assert "trusera:flags" in prop_names


class TestSARIFSchemaValidation:
    """Tests for SARIF output schema validation."""

    def test_sarif_valid_json_output(self, sample_scan_result):
        """Test that SARIF reporter produces valid JSON."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)

        # Should parse as JSON
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_sarif_required_fields(self, sample_scan_result):
        """Test that SARIF output has all required top-level fields."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        # Required fields per SARIF 2.1.0 spec
        assert "$schema" in parsed
        assert "version" in parsed
        assert "runs" in parsed

        # Verify values
        assert "sarif-schema-2.1.0.json" in parsed["$schema"]
        assert parsed["version"] == "2.1.0"
        assert isinstance(parsed["runs"], list)
        assert len(parsed["runs"]) >= 1

    def test_sarif_run_structure(self, sample_scan_result):
        """Test that each run has required structure."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        for run in parsed["runs"]:
            assert "tool" in run
            assert "results" in run
            assert isinstance(run["tool"], dict)
            assert isinstance(run["results"], list)

    def test_sarif_tool_driver(self, sample_scan_result):
        """Test that tool.driver has required fields."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        driver = parsed["runs"][0]["tool"]["driver"]
        assert "name" in driver
        assert driver["name"] == "ai-bom"
        assert "organization" in driver
        assert driver["organization"] == "Trusera"
        assert "version" in driver
        assert "informationUri" in driver
        assert "rules" in driver
        assert isinstance(driver["rules"], list)

    def test_sarif_result_required_fields(self, sample_scan_result):
        """Test that each result has required fields."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        results = parsed["runs"][0]["results"]
        assert len(results) >= 1

        for result in results:
            # Required per SARIF spec
            assert "ruleId" in result
            assert "message" in result
            assert "level" in result
            assert isinstance(result["ruleId"], str)
            assert isinstance(result["message"], dict)
            assert "text" in result["message"]
            assert result["level"] in ["none", "note", "warning", "error"]

    def test_sarif_severity_mapping(self):
        """Test that severity levels are correctly mapped to SARIF levels."""
        test_cases = [
            (Severity.critical, "error"),
            (Severity.high, "warning"),
            (Severity.medium, "note"),
            (Severity.low, "note"),
        ]

        for severity, expected_level in test_cases:
            component = _make_component(
                risk=RiskAssessment(score=50, severity=severity, factors=["test"])
            )
            result = ScanResult(target_path="/test/path")
            result.components = [component]
            result.build_summary()

            reporter = SARIFReporter()
            output = reporter.render(result)
            parsed = json.loads(output)

            assert parsed["runs"][0]["results"][0]["level"] == expected_level

    def test_sarif_locations_present(self, sample_scan_result):
        """Test that results include location information."""
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        parsed = json.loads(output)

        results = parsed["runs"][0]["results"]
        for result in results:
            assert "locations" in result
            assert isinstance(result["locations"], list)
            assert len(result["locations"]) >= 1

            location = result["locations"][0]
            assert "physicalLocation" in location
            assert "artifactLocation" in location["physicalLocation"]
            assert "uri" in location["physicalLocation"]["artifactLocation"]

    def test_sarif_line_numbers(self):
        """Test that line numbers are included when available."""
        component = _make_component(location=SourceLocation(file_path="app.py", line_number=42))
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        physical_location = parsed["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        assert "region" in physical_location
        assert physical_location["region"]["startLine"] == 42

    @pytest.mark.skipif(not JSONSCHEMA_AVAILABLE, reason="jsonschema not installed")
    def test_sarif_schema_validation(self, multi_component_result):
        """Test that output validates against SARIF schema."""
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        parsed = json.loads(output)

        # Validate against schema
        validator = Draft7Validator(SARIF_SCHEMA)
        errors = list(validator.iter_errors(parsed))
        assert len(errors) == 0, f"Schema validation errors: {errors}"

    def test_sarif_empty_components(self):
        """Test that empty component list produces valid SARIF output."""
        result = ScanResult(target_path="/test/path")
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        assert parsed["version"] == "2.1.0"
        assert parsed["runs"][0]["results"] == []
        assert isinstance(parsed["runs"][0]["results"], list)

    def test_sarif_special_characters_in_messages(self):
        """Test that special characters in messages don't break output."""
        component = _make_component(
            name="test<>&\"quotes'",
            provider="Provider & Co.",
            model_name="model-v1.0",
            flags=["flag-1", "flag-2"],
        )
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        message_text = parsed["runs"][0]["results"][0]["message"]["text"]
        assert "test<>&\"quotes'" in message_text

    def test_sarif_properties_metadata(self, critical_component):
        """Test that result properties include component metadata."""
        result = ScanResult(target_path="/test/path")
        result.components = [critical_component]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        properties = parsed["runs"][0]["results"][0]["properties"]
        assert "risk_score" in properties
        assert "component_type" in properties
        assert "usage_type" in properties
        assert "source_scanner" in properties
        assert "flags" in properties

    def test_sarif_rule_deduplication(self):
        """Test that duplicate components share the same rule."""
        component1 = _make_component(name="openai", provider="OpenAI")
        component2 = _make_component(name="openai", provider="OpenAI")
        result = ScanResult(target_path="/test/path")
        result.components = [component1, component2]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        rules = parsed["runs"][0]["tool"]["driver"]["rules"]
        results = parsed["runs"][0]["results"]

        # Should have 1 rule for 2 identical components
        assert len(rules) == 1
        assert len(results) == 2
        assert results[0]["ruleId"] == results[1]["ruleId"]

    def test_sarif_relative_path_calculation(self):
        """Test that file paths are made relative to target."""
        component = _make_component(location=SourceLocation(file_path="/test/path/subdir/app.py"))
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        uri = parsed["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        # Should be relative
        assert not uri.startswith("/test/path")
        assert "app.py" in uri

    def test_sarif_dependency_file_fallback(self):
        """Test that dependency files get fallback location."""
        component = _make_component(location=SourceLocation(file_path="dependency files"))
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        reporter = SARIFReporter()
        output = reporter.render(result)
        parsed = json.loads(output)

        uri = parsed["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        assert uri == "."


class TestJSONReporterOutput:
    """Tests for JSON reporter output (CycloneDX is the JSON format)."""

    def test_json_reporter_is_valid_json(self, sample_scan_result):
        """Test that JSON reporter output is valid JSON."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)

        # Should parse without errors
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_output_pretty_printed(self, sample_scan_result):
        """Test that JSON output is formatted with indentation."""
        reporter = CycloneDXReporter()
        output = reporter.render(sample_scan_result)

        # Should contain indentation (pretty-printed)
        assert "  " in output or "\t" in output
        assert "\n" in output

    def test_json_roundtrip(self, multi_component_result):
        """Test that JSON can be parsed and re-serialized."""
        reporter = CycloneDXReporter()
        output1 = reporter.render(multi_component_result)
        parsed = json.loads(output1)
        output2 = json.dumps(parsed, indent=2)

        # Both should be valid and represent the same data
        assert json.loads(output1) == json.loads(output2)


class TestOutputRobustness:
    """Tests for robustness of output generation."""

    def test_all_component_types(self):
        """Test that all component types can be serialized."""
        for comp_type in ComponentType:
            component = _make_component(type=comp_type)
            result = ScanResult(target_path="/test/path")
            result.components = [component]
            result.build_summary()

            # CycloneDX
            cdx_reporter = CycloneDXReporter()
            cdx_output = cdx_reporter.render(result)
            cdx_parsed = json.loads(cdx_output)
            assert len(cdx_parsed["components"]) == 1

            # SARIF
            sarif_reporter = SARIFReporter()
            sarif_output = sarif_reporter.render(result)
            sarif_parsed = json.loads(sarif_output)
            assert len(sarif_parsed["runs"][0]["results"]) == 1

    def test_all_usage_types(self):
        """Test that all usage types can be serialized."""
        for usage_type in UsageType:
            component = _make_component(usage_type=usage_type)
            result = ScanResult(target_path="/test/path")
            result.components = [component]
            result.build_summary()

            # CycloneDX
            cdx_reporter = CycloneDXReporter()
            cdx_output = cdx_reporter.render(result)
            cdx_parsed = json.loads(cdx_output)
            assert len(cdx_parsed["components"]) == 1

    def test_unicode_content(self):
        """Test that Unicode characters are handled correctly."""
        component = _make_component(
            name="测试组件",
            provider="Провайдер",
            model_name="モデル-v1.0",
        )
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        # CycloneDX
        cdx_reporter = CycloneDXReporter()
        cdx_output = cdx_reporter.render(result)
        cdx_parsed = json.loads(cdx_output)
        assert cdx_parsed["components"][0]["name"] == "测试组件"

        # SARIF
        sarif_reporter = SARIFReporter()
        sarif_output = sarif_reporter.render(result)
        sarif_parsed = json.loads(sarif_output)
        assert "测试组件" in sarif_parsed["runs"][0]["results"][0]["message"]["text"]

    def test_multiple_risk_factors(self):
        """Test that multiple risk factors are serialized correctly."""
        component = _make_component(
            risk=RiskAssessment(
                score=80,
                severity=Severity.critical,
                factors=[
                    "Hardcoded API key detected",
                    "Shadow AI component",
                    "Internet-facing endpoint",
                ],
                owasp_categories=["LLM01", "LLM02"],
            )
        )
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        # CycloneDX
        cdx_reporter = CycloneDXReporter()
        cdx_output = cdx_reporter.render(result)
        cdx_parsed = json.loads(cdx_output)
        properties = cdx_parsed["components"][0]["properties"]
        risk_factors_prop = [p for p in properties if p["name"] == "trusera:risk_factors"]
        assert len(risk_factors_prop) == 1
        assert "Hardcoded API key" in risk_factors_prop[0]["value"]

    def test_no_version_omitted(self):
        """Test that components without version omit the version field."""
        component = _make_component(version="")
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        cdx_reporter = CycloneDXReporter()
        cdx_output = cdx_reporter.render(result)
        cdx_parsed = json.loads(cdx_output)

        # Version field should be omitted when empty or "unknown"
        assert "version" not in cdx_parsed["components"][0]

    def test_valid_version_included(self):
        """Test that components with a valid version include it."""
        component = _make_component(version="1.2.3")
        result = ScanResult(target_path="/test/path")
        result.components = [component]
        result.build_summary()

        cdx_reporter = CycloneDXReporter()
        cdx_output = cdx_reporter.render(result)
        cdx_parsed = json.loads(cdx_output)

        assert cdx_parsed["components"][0]["version"] == "1.2.3"
