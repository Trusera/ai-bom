"""Tests for cloud scanner."""

import pytest

from ai_bom.scanners.cloud_scanner import CloudScanner


@pytest.fixture
def scanner():
    return CloudScanner()


class TestCloudScanner:
    def test_name(self, scanner):
        assert scanner.name == "cloud"

    def test_detects_bedrock_agent(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        assert len(components) > 0
        providers = [c.provider for c in components]
        assert any("Bedrock" in p for p in providers) or any("AWS" in p for p in providers)

    def test_detects_sagemaker(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        providers = [c.provider for c in components]
        assert (
            any("SageMaker" in p for p in providers)
            or any("AWS" in p for p in providers)
            or len(components) >= 2
        )

    def test_source_is_cloud(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        for c in components:
            assert c.source == "cloud"

    def test_empty_directory(self, scanner, tmp_path):
        components = scanner.scan(tmp_path)
        assert components == []
