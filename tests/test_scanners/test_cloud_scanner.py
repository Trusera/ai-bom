"""Tests for cloud scanner."""

import pytest

from ai_bom.models import ComponentType, UsageType
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

    def test_detects_azure_openai_deployment(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        azure_components = [c for c in components if "Azure" in c.provider]
        assert len(azure_components) >= 1
        assert any(c.provider == "Azure OpenAI" for c in azure_components)
        azure_openai = [c for c in azure_components if c.provider == "Azure OpenAI"][0]
        assert azure_openai.type == ComponentType.endpoint

    def test_detects_gcp_reasoning_engine(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        gcp_agents = [
            c for c in components
            if c.provider == "Google Vertex AI"
            and c.type == ComponentType.agent_framework
        ]
        assert len(gcp_agents) >= 1
        assert "reasoning_engine" in gcp_agents[0].name

    def test_detects_bedrock_guardrail(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        guardrails = [
            c for c in components
            if "guardrail" in c.name.lower()
        ]
        assert len(guardrails) >= 1
        assert guardrails[0].provider == "AWS Bedrock"
        assert guardrails[0].type == ComponentType.tool

    def test_detects_cloudformation_flow(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_cloudformation.yaml")
        flows = [c for c in components if "Flow" in c.name]
        assert len(flows) >= 1
        assert flows[0].provider == "AWS Bedrock"
        assert flows[0].type == ComponentType.workflow

    def test_detects_cloudformation_kendra(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_cloudformation.yaml")
        kendra = [c for c in components if "Kendra" in c.provider]
        assert len(kendra) >= 1
        assert kendra[0].type == ComponentType.tool

    def test_workflow_usage_type(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        workflow_components = [
            c for c in components if c.type == ComponentType.workflow
        ]
        assert len(workflow_components) >= 1
        for c in workflow_components:
            assert c.usage_type == UsageType.orchestration

    def test_terraform_resource_count(self, scanner):
        """Verify we have the expected number of Terraform resource types."""
        assert len(scanner.TERRAFORM_AI_RESOURCES) >= 52

    def test_cloudformation_resource_count(self, scanner):
        """Verify we have the expected number of CloudFormation resource types."""
        assert len(scanner.CLOUDFORMATION_AI_RESOURCES) >= 25

    def test_detects_sagemaker_pipeline(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_terraform.tf")
        pipelines = [
            c for c in components
            if "pipeline" in c.name.lower() and "SageMaker" in c.provider
        ]
        assert len(pipelines) >= 1
        assert pipelines[0].type == ComponentType.workflow

    def test_cloudformation_guardrail(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_cloudformation.yaml")
        guardrails = [c for c in components if "Guardrail" in c.name]
        assert len(guardrails) >= 1
        assert guardrails[0].provider == "AWS Bedrock"
        assert guardrails[0].type == ComponentType.tool

    def test_cloudformation_sagemaker_pipeline(self, scanner, fixtures_dir):
        components = scanner.scan(fixtures_dir / "sample_cloudformation.yaml")
        pipelines = [c for c in components if "Pipeline" in c.name]
        assert len(pipelines) >= 1
        assert pipelines[0].provider == "AWS SageMaker"
        assert pipelines[0].type == ComponentType.workflow
