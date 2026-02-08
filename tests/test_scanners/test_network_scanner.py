"""Tests for network scanner."""
from pathlib import Path

import pytest

from ai_bom.scanners.network_scanner import NetworkScanner


@pytest.fixture
def scanner():
    return NetworkScanner()


class TestNetworkScanner:
    def test_name(self, scanner):
        assert scanner.name == "network"

    def test_detects_api_keys_in_env(self, scanner, tmp_path):
        env_file = tmp_path / ".env.example"
        # Copy fixture content
        fixtures = Path(__file__).parent.parent / "fixtures" / "sample_env"
        env_file.write_text(fixtures.read_text())
        components = scanner.scan(tmp_path)
        assert len(components) > 0

    def test_detects_openai_key(self, scanner, tmp_path):
        f = tmp_path / ".env"
        f.write_text('OPENAI_API_KEY=sk-demo1234567890abcdefghijklmnopqrstuvwxyz0000\n')
        components = scanner.scan(tmp_path)
        assert len(components) > 0
        providers = [c.provider for c in components]
        assert any("OpenAI" in p for p in providers)

    def test_source_is_network(self, scanner, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('OPENAI_API_KEY=sk-demo1234567890abcdefghijklmnopqrstuvwxyz0000\n')
        components = scanner.scan(tmp_path)
        for c in components:
            assert c.source == "network"

    def test_empty_directory(self, scanner, tmp_path):
        components = scanner.scan(tmp_path)
        assert components == []
