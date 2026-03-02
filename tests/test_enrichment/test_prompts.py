"""Tests for enrichment prompt templates."""

from ai_bom.enrichment.prompts import (
    BATCH_ENTRY_TEMPLATE,
    BATCH_USER_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)


class TestPromptTemplates:
    def test_system_prompt_requests_json(self):
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT.lower()
        assert "model_name" in SYSTEM_PROMPT
        assert "provider" in SYSTEM_PROMPT

    def test_user_prompt_template_formats(self):
        result = USER_PROMPT_TEMPLATE.format(
            component_name="openai",
            provider="OpenAI",
            snippet="from openai import OpenAI",
        )
        assert "openai" in result
        assert "OpenAI" in result
        assert "from openai import OpenAI" in result

    def test_batch_entry_template_formats(self):
        result = BATCH_ENTRY_TEMPLATE.format(
            index=1,
            component_name="anthropic",
            provider="Anthropic",
            snippet='client.messages.create(model="claude-3-opus")',
        )
        assert "Snippet 1" in result
        assert "anthropic" in result
        assert "claude-3-opus" in result

    def test_batch_user_prompt_template_formats(self):
        entry = BATCH_ENTRY_TEMPLATE.format(
            index=1,
            component_name="openai",
            provider="OpenAI",
            snippet="client = OpenAI()",
        )
        result = BATCH_USER_PROMPT_TEMPLATE.format(entries=entry)
        assert "JSON array" in result
        assert "Snippet 1" in result
