"""Tests for code scanner."""

import pytest

from ai_bom.scanners.code_scanner import CodeScanner


@pytest.fixture
def scanner():
    return CodeScanner()


class TestCodeScanner:
    def test_name(self, scanner):
        assert scanner.name == "code"

    def test_supports_directory(self, scanner, tmp_path):
        assert scanner.supports(tmp_path)

    def test_supports_python_file(self, scanner, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass")
        assert scanner.supports(f)

    def test_detects_openai_import(self, scanner, tmp_path):
        f = tmp_path / "app.py"
        f.write_text('from openai import OpenAI\nclient = OpenAI()\n')
        req = tmp_path / "requirements.txt"
        req.write_text("openai>=1.0.0\n")
        components = scanner.scan(tmp_path)
        providers = [c.provider for c in components]
        assert any("OpenAI" in p for p in providers)

    def test_detects_hardcoded_api_key(self, scanner, tmp_path):
        f = tmp_path / "app.py"
        f.write_text(
            'from openai import OpenAI\n'
            'client = OpenAI(api_key='
            '"sk-demo1234567890abcdefghijklmnopqrstuvwxyz1234")\n'
        )
        components = scanner.scan(tmp_path)
        has_key_flag = any("hardcoded_api_key" in c.flags for c in components)
        assert has_key_flag

    def test_detects_crewai(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_crew.py")
        providers = [c.provider for c in components]
        assert any("CrewAI" in p for p in providers) or any(
            "crewai" in c.name.lower() for c in components
        )

    def test_detects_langchain(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_langchain.py")
        assert len(components) > 0

    def test_detects_requirements(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_requirements.txt")
        # Should find openai, langchain, crewai from requirements
        assert len(components) >= 2

    def test_empty_directory(self, scanner, tmp_path):
        components = scanner.scan(tmp_path)
        assert components == []

    def test_source_is_code(self, scanner, tmp_path):
        f = tmp_path / "app.py"
        f.write_text('import openai\n')
        components = scanner.scan(tmp_path)
        for c in components:
            assert c.source == "code"
