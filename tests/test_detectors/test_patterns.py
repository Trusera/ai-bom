"""Tests for LLM pattern detection."""

import re

import pytest

from ai_bom.config import API_KEY_PATTERNS, KNOWN_MODEL_PATTERNS
from ai_bom.detectors.endpoint_db import detect_api_key, match_endpoint
from ai_bom.detectors.llm_patterns import LLM_PATTERNS, get_all_dep_names
from ai_bom.detectors.model_registry import lookup_model


class TestLLMPatterns:
    def test_patterns_not_empty(self):
        assert len(LLM_PATTERNS) > 15

    def test_openai_import_patterns(self):
        openai_pattern = next(p for p in LLM_PATTERNS if p.sdk_name == "OpenAI")
        assert any(
            re.search(pat, "from openai import OpenAI") for pat in openai_pattern.import_patterns
        )

    def test_anthropic_import_patterns(self):
        pattern = next(p for p in LLM_PATTERNS if p.sdk_name == "Anthropic")
        assert any(re.search(pat, "import anthropic") for pat in pattern.import_patterns)

    def test_crewai_usage_patterns(self):
        pattern = next(p for p in LLM_PATTERNS if p.sdk_name == "CrewAI")
        assert any(
            re.search(pat, "crew = Crew(agents=[a], tasks=[t])") for pat in pattern.usage_patterns
        )

    def test_get_all_dep_names(self):
        deps = get_all_dep_names()
        assert "openai" in deps
        assert "anthropic" in deps
        assert "langchain" in deps
        assert isinstance(deps, set)


class TestEndpointDB:
    def test_match_openai_endpoint(self):
        result = match_endpoint("https://api.openai.com/v1/chat/completions")
        assert result is not None
        assert result[0] == "OpenAI"

    def test_match_anthropic_endpoint(self):
        result = match_endpoint("https://api.anthropic.com/v1/messages")
        assert result is not None
        assert result[0] == "Anthropic"

    def test_no_match(self):
        result = match_endpoint("https://example.com/api")
        assert result is None

    def test_detect_openai_key(self):
        keys = detect_api_key('api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz1234"')
        assert len(keys) > 0
        assert any(k[1] == "OpenAI" for k in keys)

    def test_detect_anthropic_key(self):
        keys = detect_api_key('key = "sk-ant-demo1234567890abcdefghij"')
        assert len(keys) > 0
        assert any(k[1] == "Anthropic" for k in keys)


class TestModelRegistry:
    def test_lookup_gpt4(self):
        result = lookup_model("gpt-4o")
        assert result is not None
        assert result["provider"] == "OpenAI"

    def test_lookup_claude(self):
        result = lookup_model("claude-3-5-sonnet")
        assert result is not None
        assert result["provider"] == "Anthropic"

    def test_deprecated_model(self):
        result = lookup_model("gpt-3.5-turbo")
        assert result is not None
        assert result.get("deprecated") is True

    def test_unknown_model(self):
        result = lookup_model("completely-unknown-model-xyz")
        assert result is None


class TestAPIKeyPatterns:
    @pytest.mark.parametrize(
        "key,provider",
        [
            ("sk-abcdefghijklmnopqrstuvwxyz1234", "OpenAI"),
            ("deepseek_api_key = 'sk-abcdefghijklmnopqrstuvwxyz1234'", "DeepSeek"),
            ("sk-ant-abcdefghijklmnopqrstuvwxyz", "Anthropic"),
            ("hf_abcdefghijklmnopqrstuvwxyz", "HuggingFace"),
        ],
    )
    def test_key_patterns(self, key, provider):
        for pattern, pat_provider in API_KEY_PATTERNS:
            if re.search(pattern, key) and pat_provider == provider:
                return
        pytest.fail(f"No pattern matched {key} for {provider}")


class TestModelPatterns:
    @pytest.mark.parametrize(
        "model,expected_provider",
        [
            ("gpt-4o-mini", "OpenAI"),
            ("claude-3-opus", "Anthropic"),
            ("gemini-1.5-pro", "Google"),
            ("mistral-large", "Mistral"),
        ],
    )
    def test_model_patterns(self, model, expected_provider):
        for pattern, provider in KNOWN_MODEL_PATTERNS:
            if re.match(pattern, model) and provider == expected_provider:
                return
        pytest.fail(f"No pattern matched {model} for {expected_provider}")
