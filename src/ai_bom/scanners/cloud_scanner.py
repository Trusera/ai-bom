"""Cloud Infrastructure Scanner for Terraform and CloudFormation AI resources."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ai_bom.models import AIComponent, ComponentType, SourceLocation, UsageType
from ai_bom.scanners.base import BaseScanner


class CloudScanner(BaseScanner):
    """Scanner for Terraform and CloudFormation infrastructure-as-code files.

    Detects AI resources in cloud infrastructure definitions including:
    - AWS Bedrock agents and knowledge bases
    - AWS SageMaker endpoints and models
    - Google Vertex AI and ML Engine resources
    - Azure Cognitive Services and ML resources
    """

    name = "cloud"
    description = "Scan Terraform/CloudFormation for AI resources"

    # Terraform resource type to (provider, component_type) mapping
    TERRAFORM_AI_RESOURCES = {
        # --- AWS Bedrock ---
        "aws_bedrockagent_agent": ("AWS Bedrock", ComponentType.agent_framework),
        "aws_bedrockagent_knowledge_base": ("AWS Bedrock", ComponentType.tool),
        "aws_bedrock_custom_model": ("AWS Bedrock", ComponentType.model),
        "aws_bedrock_provisioned_model_throughput": ("AWS Bedrock", ComponentType.endpoint),
        "aws_bedrock_guardrail": ("AWS Bedrock", ComponentType.tool),
        "aws_bedrock_model_invocation_logging_configuration": ("AWS Bedrock", ComponentType.tool),
        "aws_bedrockagent_agent_action_group": ("AWS Bedrock", ComponentType.tool),
        "aws_bedrockagent_agent_alias": ("AWS Bedrock", ComponentType.agent_framework),
        "aws_bedrockagent_data_source": ("AWS Bedrock", ComponentType.tool),
        "aws_bedrockagent_flow": ("AWS Bedrock", ComponentType.workflow),
        "aws_bedrockagent_prompt": ("AWS Bedrock", ComponentType.tool),
        # --- AWS SageMaker ---
        "aws_sagemaker_endpoint": ("AWS SageMaker", ComponentType.endpoint),
        "aws_sagemaker_model": ("AWS SageMaker", ComponentType.model),
        "aws_sagemaker_endpoint_configuration": ("AWS SageMaker", ComponentType.endpoint),
        "aws_sagemaker_notebook_instance": ("AWS SageMaker", ComponentType.tool),
        "aws_sagemaker_domain": ("AWS SageMaker", ComponentType.container),
        "aws_sagemaker_pipeline": ("AWS SageMaker", ComponentType.workflow),
        "aws_sagemaker_feature_group": ("AWS SageMaker", ComponentType.tool),
        "aws_sagemaker_space": ("AWS SageMaker", ComponentType.container),
        "aws_sagemaker_app": ("AWS SageMaker", ComponentType.tool),
        "aws_sagemaker_model_package_group": ("AWS SageMaker", ComponentType.model),
        # --- AWS Comprehend ---
        "aws_comprehend_document_classifier": ("AWS Comprehend", ComponentType.model),
        "aws_comprehend_entity_recognizer": ("AWS Comprehend", ComponentType.model),
        # --- AWS Kendra ---
        "aws_kendra_index": ("AWS Kendra", ComponentType.tool),
        # --- AWS Lex ---
        "aws_lexv2models_bot": ("AWS Lex", ComponentType.agent_framework),
        # --- AWS Rekognition ---
        "aws_rekognition_project": ("AWS Rekognition", ComponentType.model),
        # --- Google Vertex AI ---
        "google_vertex_ai_endpoint": ("Google Vertex AI", ComponentType.endpoint),
        "google_vertex_ai_featurestore": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_index": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_tensorboard": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_dataset": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_metadata_store": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_deployment_resource_pool": ("Google Vertex AI", ComponentType.container),
        "google_vertex_ai_index_endpoint": ("Google Vertex AI", ComponentType.endpoint),
        "google_vertex_ai_feature_online_store": ("Google Vertex AI", ComponentType.tool),
        "google_vertex_ai_reasoning_engine": ("Google Vertex AI", ComponentType.agent_framework),
        "google_notebooks_instance": ("Google Vertex AI", ComponentType.tool),
        "google_workbench_instance": ("Google Vertex AI", ComponentType.tool),
        # --- Google ML Engine ---
        "google_ml_engine_model": ("Google ML Engine", ComponentType.model),
        # --- Google Dialogflow CX ---
        "google_dialogflow_cx_agent": ("Google Dialogflow CX", ComponentType.agent_framework),
        # --- Google Discovery Engine ---
        "google_discovery_engine_search_engine": (
            "Google Discovery Engine",
            ComponentType.endpoint,
        ),
        # --- Azure AI ---
        "azurerm_cognitive_account": ("Azure AI", ComponentType.llm_provider),
        "azurerm_cognitive_deployment": ("Azure OpenAI", ComponentType.endpoint),
        "azurerm_ai_services": ("Azure AI", ComponentType.llm_provider),
        "azurerm_ai_foundry": ("Azure AI Foundry", ComponentType.tool),
        "azurerm_ai_foundry_project": ("Azure AI Foundry", ComponentType.tool),
        # --- Azure ML ---
        "azurerm_machine_learning_workspace": ("Azure ML", ComponentType.tool),
        "azurerm_machine_learning_compute_cluster": ("Azure ML", ComponentType.container),
        "azurerm_machine_learning_compute_instance": ("Azure ML", ComponentType.container),
        "azurerm_machine_learning_inference_cluster": ("Azure ML", ComponentType.endpoint),
        "azurerm_machine_learning_synapse_spark": ("Azure ML", ComponentType.container),
        "azurerm_machine_learning_datastore_blobstorage": ("Azure ML", ComponentType.tool),
    }

    # CloudFormation resource types to (provider, component_type) mapping
    CLOUDFORMATION_AI_RESOURCES = {
        # --- Bedrock ---
        "AWS::Bedrock::Agent": ("AWS Bedrock", ComponentType.agent_framework),
        "AWS::Bedrock::KnowledgeBase": ("AWS Bedrock", ComponentType.tool),
        "AWS::Bedrock::AgentAlias": ("AWS Bedrock", ComponentType.agent_framework),
        "AWS::Bedrock::DataSource": ("AWS Bedrock", ComponentType.tool),
        "AWS::Bedrock::Flow": ("AWS Bedrock", ComponentType.workflow),
        "AWS::Bedrock::FlowAlias": ("AWS Bedrock", ComponentType.workflow),
        "AWS::Bedrock::Guardrail": ("AWS Bedrock", ComponentType.tool),
        "AWS::Bedrock::Prompt": ("AWS Bedrock", ComponentType.tool),
        "AWS::Bedrock::ApplicationInferenceProfile": ("AWS Bedrock", ComponentType.endpoint),
        # --- SageMaker ---
        "AWS::SageMaker::Endpoint": ("AWS SageMaker", ComponentType.endpoint),
        "AWS::SageMaker::Model": ("AWS SageMaker", ComponentType.model),
        "AWS::SageMaker::EndpointConfig": ("AWS SageMaker", ComponentType.endpoint),
        "AWS::SageMaker::NotebookInstance": ("AWS SageMaker", ComponentType.tool),
        "AWS::SageMaker::Domain": ("AWS SageMaker", ComponentType.container),
        "AWS::SageMaker::Pipeline": ("AWS SageMaker", ComponentType.workflow),
        "AWS::SageMaker::FeatureGroup": ("AWS SageMaker", ComponentType.tool),
        "AWS::SageMaker::ModelPackage": ("AWS SageMaker", ComponentType.model),
        "AWS::SageMaker::ModelPackageGroup": ("AWS SageMaker", ComponentType.model),
        "AWS::SageMaker::InferenceComponent": ("AWS SageMaker", ComponentType.endpoint),
        "AWS::SageMaker::Space": ("AWS SageMaker", ComponentType.container),
        # --- Comprehend ---
        "AWS::Comprehend::DocumentClassifier": ("AWS Comprehend", ComponentType.model),
        "AWS::Comprehend::Flywheel": ("AWS Comprehend", ComponentType.workflow),
        # --- Kendra ---
        "AWS::Kendra::Index": ("AWS Kendra", ComponentType.tool),
        # --- Lex ---
        "AWS::Lex::Bot": ("AWS Lex", ComponentType.agent_framework),
        # --- Rekognition ---
        "AWS::Rekognition::Project": ("AWS Rekognition", ComponentType.model),
    }

    # Patterns for GPU instance types
    GPU_INSTANCE_PATTERN = re.compile(
        r"ml\.(g\d+|p\d+|inf\d+|trn\d+)\.\w+", re.IGNORECASE
    )

    def supports(self, path: Path) -> bool:
        """Check if path contains Terraform or CloudFormation files.

        Args:
            path: Path to check (file or directory)

        Returns:
            True if path is a .tf file or directory containing .tf/.yml/.yaml files
        """
        if path.is_file():
            # Support .tf files and potential CloudFormation templates
            ext = path.suffix.lower()
            if ext == ".tf":
                return True
            if ext in {".yml", ".yaml", ".json"}:
                # Could be a CloudFormation template - let scan handle detection
                return True
            return False

        # For directories, check if any .tf or CloudFormation files exist
        if path.is_dir():
            # Check for .tf files
            try:
                for file in path.rglob("*.tf"):
                    return True
            except (OSError, PermissionError):
                pass

            # Check for potential CloudFormation templates
            try:
                for pattern in ["*.yml", "*.yaml", "*.json"]:
                    for file in path.glob(pattern):
                        # Quick check if it looks like CloudFormation
                        if self._is_cloudformation_file(file):
                            return True
            except (OSError, PermissionError):
                pass

        return False

    def scan(self, path: Path) -> list[AIComponent]:
        """Scan Terraform and CloudFormation files for AI resources.

        Args:
            path: File or directory path to scan

        Returns:
            List of detected AI components from infrastructure definitions
        """
        components: list[AIComponent] = []

        if path.is_file():
            components.extend(self._scan_file(path))
        elif path.is_dir():
            # Scan all .tf files
            for tf_file in self.iter_files(path, extensions={".tf"}):
                components.extend(self._scan_file(tf_file))

            # Scan potential CloudFormation files
            for yaml_file in self.iter_files(path, extensions={".yml", ".yaml"}):
                if self._is_cloudformation_file(yaml_file):
                    components.extend(self._scan_file(yaml_file))

            for json_file in self.iter_files(path, extensions={".json"}):
                if self._is_cloudformation_file(json_file):
                    components.extend(self._scan_file(json_file))

        return components

    def _scan_file(self, file_path: Path) -> list[AIComponent]:
        """Scan a single infrastructure file.

        Args:
            file_path: Path to the infrastructure file

        Returns:
            List of detected AI components
        """
        ext = file_path.suffix.lower()

        if ext == ".tf":
            return self._scan_terraform(file_path)
        elif ext in {".yml", ".yaml", ".json"}:
            if self._is_cloudformation_file(file_path):
                return self._scan_cloudformation(file_path)

        return []

    def _scan_terraform(self, file_path: Path) -> list[AIComponent]:
        """Scan a Terraform file for AI resources using regex.

        Args:
            file_path: Path to the .tf file

        Returns:
            List of detected AI components
        """
        components: list[AIComponent] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            # Silently skip files that can't be read
            return components

        lines = content.split("\n")

        # Pattern to match Terraform resource blocks
        # Matches: resource "type" "name" {
        resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')

        for line_num, line in enumerate(lines, start=1):
            match = resource_pattern.search(line)
            if match:
                resource_type = match.group(1)
                resource_name = match.group(2)

                if resource_type in self.TERRAFORM_AI_RESOURCES:
                    provider, comp_type = self.TERRAFORM_AI_RESOURCES[resource_type]

                    # Extract context snippet (current line + next 5 lines)
                    context_lines = lines[line_num - 1 : line_num + 5]
                    context = "\n".join(context_lines).strip()

                    # Extract additional metadata from the resource block
                    metadata = self._extract_terraform_metadata(
                        content, line_num - 1, lines
                    )

                    # Determine model name from metadata
                    model_name = metadata.get(
                        "model_id", metadata.get("foundation_model", ""),
                    )

                    # Create component
                    component = AIComponent(
                        name=f"{resource_type}.{resource_name}",
                        type=comp_type,
                        provider=provider,
                        model_name=model_name,
                        location=SourceLocation(
                            file_path=str(file_path.resolve()),
                            line_number=line_num,
                            context_snippet=context[:200],  # Limit context size
                        ),
                        usage_type=self._infer_usage_type(comp_type, metadata),
                        metadata=metadata,
                        source="cloud",
                    )

                    # Add flags for GPU instances
                    if "instance_type" in metadata:
                        instance_type = metadata["instance_type"]
                        if self.GPU_INSTANCE_PATTERN.match(instance_type):
                            component.flags.append("gpu_instance")

                    components.append(component)

        return components

    def _extract_terraform_metadata(
        self, content: str, start_line: int, lines: list[str]
    ) -> dict[str, Any]:
        """Extract metadata from a Terraform resource block.

        Args:
            content: Full file content
            start_line: Line number where resource block starts (0-indexed)
            lines: List of all lines in the file

        Returns:
            Dictionary of extracted metadata
        """
        metadata: dict[str, Any] = {}

        # Find the resource block boundaries
        # Start from the resource line and find matching braces
        brace_count = 0
        block_lines: list[str] = []
        in_block = False

        for i in range(start_line, len(lines)):
            line = lines[i]

            if "{" in line and not in_block:
                in_block = True

            if in_block:
                block_lines.append(line)
                brace_count += line.count("{")
                brace_count -= line.count("}")

                if brace_count == 0:
                    break

        block_text = "\n".join(block_lines)

        # Extract common AI-related properties
        # foundation_model = "..."
        foundation_model_match = re.search(
            r'foundation_model\s*=\s*"([^"]+)"', block_text
        )
        if foundation_model_match:
            metadata["foundation_model"] = foundation_model_match.group(1)

        # model_id = "..."
        model_id_match = re.search(r'model_id\s*=\s*"([^"]+)"', block_text)
        if model_id_match:
            metadata["model_id"] = model_id_match.group(1)

        # instance_type = "..."
        instance_type_match = re.search(r'instance_type\s*=\s*"([^"]+)"', block_text)
        if instance_type_match:
            metadata["instance_type"] = instance_type_match.group(1)

        # model_name = "..."
        model_name_match = re.search(r'model_name\s*=\s*"([^"]+)"', block_text)
        if model_name_match:
            metadata["model_name"] = model_name_match.group(1)

        # endpoint_name = "..."
        endpoint_name_match = re.search(r'endpoint_name\s*=\s*"([^"]+)"', block_text)
        if endpoint_name_match:
            metadata["endpoint_name"] = endpoint_name_match.group(1)

        # kind = "..." (common in GCP resources)
        kind_match = re.search(r'kind\s*=\s*"([^"]+)"', block_text)
        if kind_match:
            metadata["kind"] = kind_match.group(1)

        # display_name = "..." (common in Azure/GCP resources)
        display_name_match = re.search(r'display_name\s*=\s*"([^"]+)"', block_text)
        if display_name_match:
            metadata["display_name"] = display_name_match.group(1)

        # description = "..." (common across providers)
        description_match = re.search(r'description\s*=\s*"([^"]+)"', block_text)
        if description_match:
            metadata["description"] = description_match.group(1)

        return metadata

    def _scan_cloudformation(self, file_path: Path) -> list[AIComponent]:
        """Scan a CloudFormation template for AI resources.

        Args:
            file_path: Path to the CloudFormation template (YAML or JSON)

        Returns:
            List of detected AI components
        """
        components: list[AIComponent] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            # Parse YAML or JSON
            if file_path.suffix.lower() in {".yml", ".yaml"}:
                # CloudFormation uses custom tags like !Ref, !GetAtt, etc.
                # We need a custom constructor to handle them
                data = self._parse_cloudformation_yaml(content)
            else:
                data = json.loads(content)

            if not isinstance(data, dict):
                return components

            # CloudFormation templates have a "Resources" section
            resources = data.get("Resources", {})
            if not isinstance(resources, dict):
                return components

            # Scan each resource
            for resource_name, resource_def in resources.items():
                if not isinstance(resource_def, dict):
                    continue

                resource_type = resource_def.get("Type", "")
                if resource_type in self.CLOUDFORMATION_AI_RESOURCES:
                    provider, comp_type = self.CLOUDFORMATION_AI_RESOURCES[
                        resource_type
                    ]

                    # Extract properties
                    properties = resource_def.get("Properties", {})
                    if not isinstance(properties, dict):
                        properties = {}

                    # Extract model name (try various property names)
                    model_name = (
                        properties.get("ModelId", "")
                        or properties.get("ModelName", "")
                        or properties.get("FoundationModel", "")
                        or properties.get("AgentName", "")
                        or properties.get("FlowName", "")
                        or properties.get("GuardrailName", "")
                        or properties.get("PipelineName", "")
                    )

                    # Create metadata
                    metadata = {
                        "resource_type": resource_type,
                        "properties": properties,
                    }

                    # Extract endpoint name if present
                    endpoint_name = properties.get("EndpointName", "")
                    if endpoint_name:
                        metadata["endpoint_name"] = endpoint_name

                    # Create component
                    component = AIComponent(
                        name=f"{resource_type}:{resource_name}",
                        type=comp_type,
                        provider=provider,
                        model_name=model_name,
                        location=SourceLocation(
                            file_path=str(file_path.resolve()),
                            line_number=None,  # JSON/YAML line numbers are complex
                            context_snippet=f"Resource: {resource_name}",
                        ),
                        usage_type=self._infer_usage_type(comp_type, metadata),
                        metadata=metadata,
                        source="cloud",
                    )

                    components.append(component)

        except (OSError, yaml.YAMLError, json.JSONDecodeError):
            # Silently skip files that can't be parsed
            pass

        return components

    def _parse_cloudformation_yaml(self, content: str) -> dict[str, Any]:
        """Parse CloudFormation YAML with custom tag support.

        CloudFormation uses custom YAML tags like !Ref, !GetAtt, !Sub, etc.
        This method adds constructors for these tags to return simple string values.

        Args:
            content: YAML content string

        Returns:
            Parsed YAML as dictionary
        """

        # Define a custom constructor that returns the tag value as a string
        def cloudformation_constructor(loader, node):
            """Constructor for CloudFormation intrinsic functions."""
            if isinstance(node, yaml.ScalarNode):
                return loader.construct_scalar(node)
            elif isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node)
            elif isinstance(node, yaml.MappingNode):
                return loader.construct_mapping(node)
            return None

        # Create a custom YAML loader
        loader = yaml.SafeLoader

        # Add constructors for common CloudFormation tags
        cf_tags = [
            "!Ref",
            "!GetAtt",
            "!Sub",
            "!Join",
            "!Select",
            "!Split",
            "!FindInMap",
            "!GetAZs",
            "!ImportValue",
            "!Base64",
        ]

        for tag in cf_tags:
            yaml.add_constructor(tag, cloudformation_constructor, Loader=loader)

        return yaml.load(content, Loader=loader)

    def _is_cloudformation_file(self, file_path: Path) -> bool:
        """Check if a file is a CloudFormation template.

        Args:
            file_path: Path to check

        Returns:
            True if the file appears to be a CloudFormation template
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            # Check for CloudFormation markers
            if "AWSTemplateFormatVersion" in content:
                return True

            if "AWS::" in content and (
                "Resources:" in content or '"Resources"' in content
            ):
                return True

            # Try parsing and checking structure
            if file_path.suffix.lower() in {".yml", ".yaml"}:
                data = yaml.safe_load(content)
            elif file_path.suffix.lower() == ".json":
                data = json.loads(content)
            else:
                return False

            if isinstance(data, dict):
                # CloudFormation templates have AWSTemplateFormatVersion or Resources
                if "AWSTemplateFormatVersion" in data or "Resources" in data:
                    return True

        except (OSError, yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError):
            pass

        return False

    def _infer_usage_type(
        self, component_type: ComponentType, metadata: dict[str, Any]
    ) -> UsageType:
        """Infer usage type from component type and metadata.

        Args:
            component_type: The component type
            metadata: Extracted metadata

        Returns:
            Inferred usage type
        """
        # Agent frameworks are used for agents
        if component_type == ComponentType.agent_framework:
            return UsageType.agent

        # Models and endpoints could be various types
        if component_type in {ComponentType.model, ComponentType.endpoint}:
            # Check if model name suggests embedding
            model_name = metadata.get(
                "model_id", metadata.get("foundation_model", ""),
            )
            if "embed" in model_name.lower():
                return UsageType.embedding

            # Default to completion for LLM endpoints
            return UsageType.completion

        # Workflows are used for orchestration
        if component_type == ComponentType.workflow:
            return UsageType.orchestration

        # Tools are used for tool_use
        if component_type == ComponentType.tool:
            return UsageType.tool_use

        # Containers might be for orchestration
        if component_type == ComponentType.container:
            return UsageType.orchestration

        return UsageType.unknown
