"""Tests for the LLM enricher module."""

from __future__ import annotations

from unittest.mock import patch

from ai_bom.enrichment.llm_enricher import (
    _apply_result,
    _parse_batch_result,
    _parse_single_result,
    _read_context,
    enrich_components,
)
from ai_bom.models import AIComponent, ComponentType, SourceLocation, UsageType


def _make_component(
    name: str = "openai",
    comp_type: ComponentType = ComponentType.llm_provider,
    provider: str = "OpenAI",
    model_name: str = "",
    file_path: str = "app.py",
    line_number: int | None = 5,
    snippet: str = "from openai import OpenAI",
) -> AIComponent:
    return AIComponent(
        name=name,
        type=comp_type,
        provider=provider,
        model_name=model_name,
        location=SourceLocation(
            file_path=file_path,
            line_number=line_number,
            context_snippet=snippet,
        ),
        usage_type=UsageType.completion,
        source="code",
    )


class TestParseResults:
    def test_parse_single_valid_json(self):
        raw = '{"model_name": "gpt-4o", "provider": "OpenAI"}'
        result = _parse_single_result(raw)
        assert result["model_name"] == "gpt-4o"
        assert result["provider"] == "OpenAI"

    def test_parse_single_with_markdown_fences(self):
        raw = '```json\n{"model_name": "gpt-4o", "provider": "OpenAI"}\n```'
        result = _parse_single_result(raw)
        assert result["model_name"] == "gpt-4o"

    def test_parse_single_empty_result(self):
        raw = '{"model_name": "", "provider": ""}'
        result = _parse_single_result(raw)
        assert result["model_name"] == ""
        assert result["provider"] == ""

    def test_parse_single_invalid_json(self):
        raw = "This is not valid JSON at all"
        result = _parse_single_result(raw)
        assert result["model_name"] == ""

    def test_parse_single_empty_string(self):
        result = _parse_single_result("")
        assert result["model_name"] == ""

    def test_parse_batch_valid_json(self):
        raw = (
            '[{"model_name": "gpt-4o", "provider": "OpenAI"}, '
            '{"model_name": "claude-3-opus", "provider": "Anthropic"}]'
        )
        results = _parse_batch_result(raw, 2)
        assert len(results) == 2
        assert results[0]["model_name"] == "gpt-4o"
        assert results[1]["model_name"] == "claude-3-opus"

    def test_parse_batch_with_markdown_fences(self):
        raw = '```json\n[{"model_name": "gpt-4o", "provider": "OpenAI"}]\n```'
        results = _parse_batch_result(raw, 1)
        assert len(results) == 1
        assert results[0]["model_name"] == "gpt-4o"

    def test_parse_batch_invalid_json(self):
        results = _parse_batch_result("not json", 3)
        assert len(results) == 3
        assert all(r["model_name"] == "" for r in results)


class TestApplyResult:
    def test_applies_model_name(self):
        comp = _make_component()
        _apply_result(comp, {"model_name": "gpt-4o", "provider": "OpenAI"})
        assert comp.model_name == "gpt-4o"
        assert "llm_enriched" in comp.flags

    def test_skips_empty_model_name(self):
        comp = _make_component()
        _apply_result(comp, {"model_name": "", "provider": ""})
        assert comp.model_name == ""
        assert "llm_enriched" not in comp.flags

    def test_adds_deprecated_flag_from_registry(self):
        comp = _make_component(provider="")
        _apply_result(comp, {"model_name": "gpt-3.5-turbo", "provider": ""})
        assert comp.model_name == "gpt-3.5-turbo"
        assert "deprecated_model" in comp.flags
        assert comp.provider == "OpenAI"

    def test_preserves_existing_provider(self):
        comp = _make_component(provider="CustomProvider")
        _apply_result(comp, {"model_name": "gpt-4o", "provider": "OpenAI"})
        assert comp.provider == "CustomProvider"

    def test_sets_provider_from_llm_when_no_registry_match(self):
        comp = _make_component(provider="")
        _apply_result(comp, {"model_name": "my-custom-model", "provider": "MyProvider"})
        assert comp.provider == "MyProvider"

    def test_sets_provider_from_registry_when_empty(self):
        comp = _make_component(provider="")
        _apply_result(comp, {"model_name": "claude-3-opus-20240229", "provider": ""})
        assert comp.provider == "Anthropic"


class TestReadContext:
    def test_reads_lines_around_detection(self, tmp_path):
        f = tmp_path / "app.py"
        lines = [f"line {i}" for i in range(1, 31)]
        f.write_text("\n".join(lines))

        result = _read_context("app.py", 15, tmp_path)
        assert "line 5" in result
        assert "line 15" in result
        assert "line 25" in result

    def test_returns_empty_for_missing_file(self, tmp_path):
        result = _read_context("nonexistent.py", 5, tmp_path)
        assert result == ""

    def test_returns_empty_for_dependency_files(self, tmp_path):
        result = _read_context("dependency files", None, tmp_path)
        assert result == ""

    def test_reads_top_lines_without_line_number(self, tmp_path):
        f = tmp_path / "app.py"
        lines = [f"line {i}" for i in range(1, 31)]
        f.write_text("\n".join(lines))

        result = _read_context("app.py", None, tmp_path)
        assert "line 1" in result
        assert "line 20" in result


class TestEnrichComponents:
    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_enriches_eligible_component(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text(
            "from openai import OpenAI\n"
            "client = OpenAI()\n"
            'response = client.chat.completions.create(model="gpt-4o", messages=[])\n'
        )
        comp = _make_component(file_path="app.py", line_number=3, snippet="")
        mock_llm.return_value = '{"model_name": "gpt-4o", "provider": "OpenAI"}'

        count = enrich_components([comp], scan_path=tmp_path, batch_size=1)

        assert count == 1
        assert comp.model_name == "gpt-4o"
        assert "llm_enriched" in comp.flags
        mock_llm.assert_called_once()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_skips_component_with_existing_model_name(self, mock_llm, tmp_path):
        comp = _make_component(model_name="gpt-4o")

        count = enrich_components([comp], scan_path=tmp_path)

        assert count == 0
        mock_llm.assert_not_called()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_skips_non_model_component(self, mock_llm, tmp_path):
        comp = _make_component(comp_type=ComponentType.container, name="ollama/ollama")

        count = enrich_components([comp], scan_path=tmp_path)

        assert count == 0
        mock_llm.assert_not_called()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_skips_agent_framework_component(self, mock_llm, tmp_path):
        comp = _make_component(comp_type=ComponentType.agent_framework, name="langchain")

        count = enrich_components([comp], scan_path=tmp_path)

        assert count == 0
        mock_llm.assert_not_called()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_skips_component_with_no_snippet_and_unreadable_file(self, mock_llm, tmp_path):
        comp = _make_component(file_path="nonexistent.py", snippet="")

        count = enrich_components([comp], scan_path=tmp_path)

        assert count == 0
        mock_llm.assert_not_called()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_handles_llm_api_error_gracefully(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\nclient = OpenAI()\n")
        comp = _make_component(file_path="app.py", line_number=1, snippet="")
        mock_llm.side_effect = Exception("API Error")

        count = enrich_components([comp], scan_path=tmp_path, batch_size=1)

        assert count == 0
        assert comp.model_name == ""

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_handles_invalid_json_response(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\nclient = OpenAI()\n")
        comp = _make_component(file_path="app.py", line_number=1, snippet="")
        mock_llm.return_value = "Sorry, I cannot process this request."

        count = enrich_components([comp], scan_path=tmp_path, batch_size=1)

        assert count == 0
        assert comp.model_name == ""

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_model_name_cross_referenced_with_registry(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\nclient = OpenAI()\n")
        comp = _make_component(file_path="app.py", line_number=1, provider="", snippet="")
        mock_llm.return_value = '{"model_name": "gpt-4o-2024-05-13", "provider": ""}'

        count = enrich_components([comp], scan_path=tmp_path, batch_size=1)

        assert count == 1
        assert comp.model_name == "gpt-4o-2024-05-13"
        assert comp.provider == "OpenAI"

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_batch_enrichment(self, mock_llm, tmp_path):
        f1 = tmp_path / "app.py"
        f1.write_text('from openai import OpenAI\nclient.chat.completions.create(model="gpt-4o")\n')
        f2 = tmp_path / "bot.py"
        f2.write_text('import anthropic\nclient.messages.create(model="claude-3-opus-20240229")\n')
        comp1 = _make_component(file_path="app.py", line_number=2, snippet="")
        comp2 = _make_component(
            name="anthropic",
            provider="Anthropic",
            file_path="bot.py",
            line_number=2,
            snippet="",
        )
        mock_llm.return_value = (
            '[{"model_name": "gpt-4o", "provider": "OpenAI"}, '
            '{"model_name": "claude-3-opus-20240229", "provider": "Anthropic"}]'
        )

        count = enrich_components([comp1, comp2], scan_path=tmp_path, batch_size=5)

        assert count == 2
        assert comp1.model_name == "gpt-4o"
        assert comp2.model_name == "claude-3-opus-20240229"
        mock_llm.assert_called_once()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_batch_fallback_to_individual_on_error(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\nclient = OpenAI()\n")
        f2 = tmp_path / "bot.py"
        f2.write_text("import anthropic\nclient = anthropic.Anthropic()\n")

        comp1 = _make_component(file_path="app.py", line_number=1, snippet="")
        comp2 = _make_component(
            name="anthropic",
            provider="Anthropic",
            file_path="bot.py",
            line_number=1,
            snippet="",
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Batch failed")
            if call_count == 2:
                return '{"model_name": "gpt-4o", "provider": "OpenAI"}'
            return '{"model_name": "claude-3-opus", "provider": "Anthropic"}'

        mock_llm.side_effect = side_effect

        count = enrich_components([comp1, comp2], scan_path=tmp_path, batch_size=5)

        assert count == 2
        assert comp1.model_name == "gpt-4o"
        assert comp2.model_name == "claude-3-opus"
        assert call_count == 3

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_reads_extra_context_from_source(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text(
            "import os\n"
            "from openai import OpenAI\n"
            "\n"
            "client = OpenAI()\n"
            'response = client.chat.completions.create(model="gpt-4o", messages=[])\n'
            "print(response)\n"
        )
        comp = _make_component(
            file_path="app.py",
            line_number=5,
            snippet="from openai import OpenAI",
        )
        mock_llm.return_value = '{"model_name": "gpt-4o", "provider": "OpenAI"}'

        enrich_components([comp], scan_path=tmp_path, batch_size=1)

        call_args = mock_llm.call_args[0][0]
        user_content = call_args[1]["content"]
        assert 'model="gpt-4o"' in user_content

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_returns_zero_for_empty_list(self, mock_llm, tmp_path):
        count = enrich_components([], scan_path=tmp_path)
        assert count == 0
        mock_llm.assert_not_called()

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_falls_back_to_context_snippet(self, mock_llm, tmp_path):
        comp = _make_component(
            file_path="nonexistent.py",
            snippet='client.chat.completions.create(model="gpt-4o")',
        )
        mock_llm.return_value = '{"model_name": "gpt-4o", "provider": "OpenAI"}'

        count = enrich_components([comp], scan_path=tmp_path, batch_size=1)

        assert count == 1
        assert comp.model_name == "gpt-4o"
