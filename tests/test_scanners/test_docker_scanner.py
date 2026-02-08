"""Tests for docker scanner."""

import pytest

from ai_bom.scanners.docker_scanner import DockerScanner


@pytest.fixture
def scanner():
    return DockerScanner()


class TestDockerScanner:
    def test_name(self, scanner):
        assert scanner.name == "docker"

    def test_detects_ollama_in_compose(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_docker_compose.yml")
        assert len(components) > 0
        providers = [c.provider for c in components]
        assert any("Ollama" in p for p in providers) or any(
            "ollama" in c.name.lower() for c in components
        )

    def test_detects_gpu(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_docker_compose.yml")
        gpu_components = [c for c in components if c.metadata.get("gpu")]
        assert len(gpu_components) > 0

    def test_source_is_docker(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_docker_compose.yml")
        for c in components:
            assert c.source == "docker"

    def test_empty_directory(self, scanner, tmp_path):
        components = scanner.scan(tmp_path)
        assert components == []
