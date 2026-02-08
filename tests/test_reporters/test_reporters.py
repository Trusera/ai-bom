"""Tests for report output formats."""
import json

from ai_bom.reporters import get_reporter
from ai_bom.reporters.cli_reporter import CLIReporter
from ai_bom.reporters.cyclonedx import CycloneDXReporter
from ai_bom.reporters.html_reporter import HTMLReporter
from ai_bom.reporters.markdown import MarkdownReporter
from ai_bom.reporters.sarif import SARIFReporter


class TestCLIReporter:
    def test_renders_string(self, multi_component_result):
        reporter = CLIReporter()
        output = reporter.render(multi_component_result)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_contains_component_info(self, multi_component_result):
        reporter = CLIReporter()
        output = reporter.render(multi_component_result)
        assert "openai" in output.lower() or "OpenAI" in output

    def test_empty_result(self):
        from ai_bom.models import ScanResult
        result = ScanResult(target_path="/empty")
        result.build_summary()
        reporter = CLIReporter()
        output = reporter.render(result)
        assert isinstance(output, str)


class TestCycloneDXReporter:
    def test_valid_json(self, multi_component_result):
        reporter = CycloneDXReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert data["bomFormat"] == "CycloneDX"
        assert data["specVersion"] == "1.6"

    def test_has_components(self, multi_component_result):
        reporter = CycloneDXReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert len(data["components"]) == len(multi_component_result.components)

    def test_has_metadata(self, multi_component_result):
        reporter = CycloneDXReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert "metadata" in data
        assert "tools" in data["metadata"]

    def test_has_trusera_properties(self, multi_component_result):
        reporter = CycloneDXReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        for comp in data["components"]:
            prop_names = [p["name"] for p in comp["properties"]]
            assert "trusera:risk_score" in prop_names
            assert "trusera:usage_type" in prop_names


class TestHTMLReporter:
    def test_renders_html(self, multi_component_result):
        reporter = HTMLReporter()
        output = reporter.render(multi_component_result)
        assert "<!DOCTYPE html>" in output or "<html" in output

    def test_self_contained(self, multi_component_result):
        reporter = HTMLReporter()
        output = reporter.render(multi_component_result)
        assert "<style>" in output
        assert "<script>" in output or "</table>" in output

    def test_contains_trusera(self, multi_component_result):
        reporter = HTMLReporter()
        output = reporter.render(multi_component_result)
        assert "trusera" in output.lower() or "Trusera" in output

    def test_write_to_file(self, multi_component_result, tmp_path):
        reporter = HTMLReporter()
        path = tmp_path / "report.html"
        reporter.write(multi_component_result, path)
        assert path.exists()
        assert path.read_text().startswith("<!DOCTYPE html>") or "<html" in path.read_text()


class TestMarkdownReporter:
    def test_renders_markdown(self, multi_component_result):
        reporter = MarkdownReporter()
        output = reporter.render(multi_component_result)
        assert "# " in output
        assert "|" in output  # Tables

    def test_has_summary(self, multi_component_result):
        reporter = MarkdownReporter()
        output = reporter.render(multi_component_result)
        assert "Summary" in output

    def test_has_recommendations(self, multi_component_result):
        reporter = MarkdownReporter()
        output = reporter.render(multi_component_result)
        assert "Recommend" in output

    def test_has_trusera(self, multi_component_result):
        reporter = MarkdownReporter()
        output = reporter.render(multi_component_result)
        assert "Trusera" in output or "trusera" in output


class TestSARIFReporter:
    def test_valid_json(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert "$schema" in data

    def test_schema_url_uses_release_branch(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert "release-2.1" in data["$schema"]
        assert "main" not in data["$schema"]

    def test_has_runs(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        assert len(data["runs"]) == 1
        run = data["runs"][0]
        assert "tool" in run
        assert "results" in run

    def test_has_rules(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        rules = data["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) > 0
        for rule in rules:
            assert "id" in rule
            assert rule["id"].startswith("ai-bom/")

    def test_has_results_with_rule_index(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        results = data["runs"][0]["results"]
        assert len(results) == len(multi_component_result.components)
        for result in results:
            assert "ruleId" in result
            assert "ruleIndex" in result
            assert isinstance(result["ruleIndex"], int)

    def test_result_levels(self, multi_component_result):
        reporter = SARIFReporter()
        output = reporter.render(multi_component_result)
        data = json.loads(output)
        results = data["runs"][0]["results"]
        valid_levels = {"error", "warning", "note"}
        for result in results:
            assert result["level"] in valid_levels

    def test_empty_components(self):
        from ai_bom.models import ScanResult
        result = ScanResult(target_path="/empty")
        result.build_summary()
        reporter = SARIFReporter()
        output = reporter.render(result)
        data = json.loads(output)
        assert data["runs"][0]["results"] == []
        assert data["runs"][0]["tool"]["driver"]["rules"] == []

    def test_component_without_file_path(self):
        from ai_bom.models import (
            AIComponent,
            ComponentType,
            ScanResult,
            SourceLocation,
            UsageType,
        )
        comp = AIComponent(
            name="openai",
            type=ComponentType.llm_provider,
            provider="OpenAI",
            location=SourceLocation(file_path="dependency files"),
            usage_type=UsageType.completion,
            source="code",
        )
        result = ScanResult(target_path="/test")
        result.components = [comp]
        result.build_summary()
        reporter = SARIFReporter()
        output = reporter.render(result)
        data = json.loads(output)
        # Result should exist but without locations
        sarif_result = data["runs"][0]["results"][0]
        assert "locations" not in sarif_result

    def test_component_without_line_number(self):
        from ai_bom.models import (
            AIComponent,
            ComponentType,
            ScanResult,
            SourceLocation,
            UsageType,
        )
        comp = AIComponent(
            name="openai",
            type=ComponentType.llm_provider,
            provider="OpenAI",
            location=SourceLocation(file_path="/test/app.py"),
            usage_type=UsageType.completion,
            source="code",
        )
        result = ScanResult(target_path="/test")
        result.components = [comp]
        result.build_summary()
        reporter = SARIFReporter()
        output = reporter.render(result)
        data = json.loads(output)
        loc = data["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        assert "region" not in loc

    def test_path_relativity(self, sample_scan_result):
        reporter = SARIFReporter()
        output = reporter.render(sample_scan_result)
        data = json.loads(output)
        results = data["runs"][0]["results"]
        for result in results:
            if "locations" in result:
                uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
                assert not uri.startswith("/"), f"Path should be relative: {uri}"
                loc = result["locations"][0]["physicalLocation"]
                assert loc["artifactLocation"]["uriBaseId"] == "%SRCROOT%"

    def test_write_to_file(self, multi_component_result, tmp_path):
        reporter = SARIFReporter()
        path = tmp_path / "results.sarif"
        reporter.write(multi_component_result, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == "2.1.0"


class TestGetReporter:
    def test_table_format(self):
        assert isinstance(get_reporter("table"), CLIReporter)

    def test_cyclonedx_format(self):
        assert isinstance(get_reporter("cyclonedx"), CycloneDXReporter)

    def test_json_format(self):
        assert isinstance(get_reporter("json"), CycloneDXReporter)

    def test_html_format(self):
        assert isinstance(get_reporter("html"), HTMLReporter)

    def test_markdown_format(self):
        assert isinstance(get_reporter("markdown"), MarkdownReporter)

    def test_sarif_format(self):
        assert isinstance(get_reporter("sarif"), SARIFReporter)

    def test_unknown_format_defaults_to_cli(self):
        assert isinstance(get_reporter("unknown"), CLIReporter)
