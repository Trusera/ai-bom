"""Tests for n8n scanner."""
import pytest

from ai_bom.scanners.n8n_scanner import N8nScanner


@pytest.fixture
def scanner():
    return N8nScanner()


class TestN8nScanner:
    def test_name(self, scanner):
        assert scanner.name == "n8n"

    def test_detects_ai_agent(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_n8n_workflow.json")
        assert len(components) > 0
        types = [c.type.value for c in components]
        assert "agent_framework" in types or "llm_provider" in types

    def test_detects_openai_model(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_n8n_workflow.json")
        providers = [c.provider for c in components]
        assert any("OpenAI" in p for p in providers)

    def test_detects_webhook_no_auth(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_n8n_workflow.json")
        flags = []
        for c in components:
            flags.extend(c.flags)
        assert "webhook_no_auth" in flags

    def test_source_is_n8n(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_n8n_workflow.json")
        for c in components:
            assert c.source == "n8n"

    def test_skips_non_n8n_json(self, scanner, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "test", "version": "1.0.0"}')
        components = scanner.scan(tmp_path)
        assert components == []

    def test_empty_directory(self, scanner, tmp_path):
        components = scanner.scan(tmp_path)
        assert components == []
