"""n8n workflow scanner for detecting AI agents and MCP usage in n8n workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ai_bom.config import API_KEY_PATTERNS, N8N_AI_NODE_TYPES
from ai_bom.models import (
    AIComponent,
    ComponentType,
    N8nWorkflowInfo,
    SourceLocation,
    UsageType,
)
from ai_bom.scanners.base import BaseScanner


class N8nScanner(BaseScanner):
    """Scanner for n8n workflow JSON files to detect AI agents and MCP usage."""

    name = "n8n"
    description = "Scan n8n workflow JSONs for AI agents & MCP"

    def supports(self, path: Path) -> bool:
        """Check if this scanner should run on the given path.

        Args:
            path: Directory or file path to check

        Returns:
            True if path is a directory or JSON file, False otherwise
        """
        return path.is_dir() or (path.is_file() and path.suffix.lower() == ".json")

    def scan(self, path: Path) -> list[AIComponent]:
        """Scan path for n8n workflow files and extract AI components.

        Args:
            path: Directory or file path to scan

        Returns:
            List of detected AI components from n8n workflows
        """
        components: list[AIComponent] = []

        # Collect all workflow files
        if path.is_file():
            workflow_files = [path]
        else:
            workflow_files = list(self.iter_files(path, extensions={".json"}))

        # Track workflows for cross-workflow analysis
        workflows: dict[str, N8nWorkflowInfo] = {}

        # First pass: scan individual workflows
        for workflow_file in workflow_files:
            try:
                workflow_data = self._load_workflow(workflow_file)
                if workflow_data is None:
                    continue

                workflow_info = self._extract_workflow_info(workflow_data, workflow_file)
                workflows[str(workflow_file)] = workflow_info

                # Extract AI components from this workflow
                workflow_components = self._extract_ai_components(
                    workflow_data, workflow_file, workflow_info
                )

                # Second pass: inspect base n8n nodes for security risks
                self._inspect_base_nodes(
                    workflow_data, workflow_file, workflow_info, workflow_components
                )

                # Apply workflow-level risk patterns
                self._apply_workflow_risks(workflow_data, workflow_components)

                components.extend(workflow_components)

            except Exception:
                # Log error but continue scanning other files
                continue

        # Second pass: detect agent chains across workflows
        self._detect_agent_chains(workflows, components)

        return components

    def _load_workflow(self, file_path: Path) -> dict[str, Any] | None:
        """Load and validate n8n workflow JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed workflow data if valid n8n workflow, None otherwise
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate this is an n8n workflow
            if not isinstance(data, dict):
                return None

            # n8n workflows have both "nodes" (list) and "connections" (dict)
            if "nodes" not in data or "connections" not in data:
                return None

            if not isinstance(data.get("nodes"), list):
                return None

            if not isinstance(data.get("connections"), dict):
                return None

            return data

        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None

    def _extract_workflow_info(
        self, workflow_data: dict[str, Any], file_path: Path
    ) -> N8nWorkflowInfo:
        """Extract metadata from n8n workflow.

        Args:
            workflow_data: Parsed workflow JSON
            file_path: Path to workflow file

        Returns:
            N8nWorkflowInfo object with metadata
        """
        workflow_name = workflow_data.get("name", file_path.stem)
        workflow_id = workflow_data.get("id", "")

        # Extract node types
        nodes = workflow_data.get("nodes", [])
        node_types = [node.get("type", "") for node in nodes]

        # Build connection map
        connections = self._parse_connections(workflow_data.get("connections", {}))

        # Detect trigger type
        trigger_type = self._detect_trigger_type(nodes)

        # Extract agent chains
        agent_chains = self._extract_agent_chains(nodes, connections)

        return N8nWorkflowInfo(
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            nodes=node_types,
            connections=connections,
            trigger_type=trigger_type,
            agent_chains=agent_chains,
        )

    def _parse_connections(
        self, connections: dict[str, Any]
    ) -> dict[str, list[str]]:
        """Parse n8n connections object into simple node->nodes mapping.

        Args:
            connections: n8n connections object

        Returns:
            Dictionary mapping node names to list of connected node names
        """
        result: dict[str, list[str]] = {}

        for source_node, connection_types in connections.items():
            connected_nodes: set[str] = set()

            if isinstance(connection_types, dict):
                for conn_type, conn_list in connection_types.items():
                    if isinstance(conn_list, list):
                        for conn_group in conn_list:
                            if isinstance(conn_group, list):
                                for conn in conn_group:
                                    if isinstance(conn, dict):
                                        target = conn.get("node")
                                        if target:
                                            connected_nodes.add(target)

            result[source_node] = list(connected_nodes)

        return result

    def _detect_trigger_type(self, nodes: list[dict[str, Any]]) -> str:
        """Detect the trigger type for the workflow.

        Args:
            nodes: List of workflow nodes

        Returns:
            Trigger type string (webhook, schedule, manual, or unknown)
        """
        for node in nodes:
            node_type = node.get("type", "")
            if "webhook" in node_type.lower():
                return "webhook"
            if "schedule" in node_type.lower() or "cron" in node_type.lower():
                return "schedule"
            if "trigger" in node_type.lower() and "manual" in node_type.lower():
                return "manual"

        return "unknown"

    def _extract_agent_chains(
        self, nodes: list[dict[str, Any]], connections: dict[str, list[str]]
    ) -> list[list[str]]:
        """Extract chains of agent nodes from workflow.

        Args:
            nodes: List of workflow nodes
            connections: Node connection mapping

        Returns:
            List of agent node name chains
        """
        agent_nodes = {
            node.get("name", "")
            for node in nodes
            if self._is_agent_node(node.get("type", ""))
        }

        chains: list[list[str]] = []

        # Find chains of connected agents
        for agent in agent_nodes:
            chain = [agent]
            current = agent

            # Follow connections forward
            while current in connections:
                next_nodes = connections[current]
                next_agents = [n for n in next_nodes if n in agent_nodes]

                if not next_agents:
                    break

                # Take first agent connection (avoid infinite loops)
                next_agent = next_agents[0]
                if next_agent in chain:
                    break

                chain.append(next_agent)
                current = next_agent

            # Only keep chains with 2+ agents
            if len(chain) > 1:
                chains.append(chain)

        return chains

    def _is_agent_node(self, node_type: str) -> bool:
        """Check if node type is an agent node.

        Args:
            node_type: Node type string

        Returns:
            True if agent node, False otherwise
        """
        return ".agent" in node_type.lower()

    def _extract_ai_components(
        self,
        workflow_data: dict[str, Any],
        file_path: Path,
        workflow_info: N8nWorkflowInfo,
    ) -> list[AIComponent]:
        """Extract AI components from workflow nodes.

        Args:
            workflow_data: Parsed workflow JSON
            file_path: Path to workflow file
            workflow_info: Workflow metadata

        Returns:
            List of AI components found in workflow
        """
        components: list[AIComponent] = []
        nodes = workflow_data.get("nodes", [])

        for node in nodes:
            node_type = node.get("type", "")

            # Check if this is an AI node
            if node_type not in N8N_AI_NODE_TYPES:
                continue

            # Map node to component
            component = self._node_to_component(node, file_path, workflow_info)
            if component:
                components.append(component)

        return components

    def _inspect_base_nodes(
        self,
        workflow_data: dict[str, Any],
        file_path: Path,
        workflow_info: N8nWorkflowInfo,
        components: list[AIComponent],
    ) -> None:
        """Inspect base n8n nodes (non-AI) for security risks.

        Checks n8n-nodes-base.httpRequest for hardcoded API keys and
        n8n-nodes-base.code for dangerous code patterns.

        Args:
            workflow_data: Parsed workflow JSON
            file_path: Path to workflow file
            workflow_info: Workflow metadata
            components: List of components to potentially add findings to
        """
        nodes = workflow_data.get("nodes", [])

        # Dangerous code patterns in n8n code nodes
        dangerous_code_patterns = [
            r"child_process",
            r"execSync\(",
            r"exec\(",
            r"spawn\(",
            r"require\(['\"]fs['\"]\)",
            r"eval\(",
        ]

        for node in nodes:
            node_type = node.get("type", "")
            node_name = node.get("name", "")
            parameters = node.get("parameters", {})

            # Skip AI nodes (already handled)
            if node_type in N8N_AI_NODE_TYPES:
                continue

            # Check httpRequest nodes for hardcoded API keys
            if node_type == "n8n-nodes-base.httpRequest":
                params_str = json.dumps(parameters)
                for pattern, provider in API_KEY_PATTERNS:
                    if re.search(pattern, params_str):
                        # Add a component for the hardcoded key
                        location = SourceLocation(
                            file_path=str(file_path.resolve()),
                            context_snippet=(
                            f"Workflow: {workflow_info.workflow_name},"
                            f" Node: {node_name}"
                        ),
                        )
                        component = AIComponent(
                            name=f"{provider} API Key in HTTP Request",
                            type=ComponentType.llm_provider,
                            provider=provider,
                            location=location,
                            usage_type=UsageType.unknown,
                            source="n8n",
                            flags=["hardcoded_credentials"],
                            metadata={
                                "workflow_name": workflow_info.workflow_name,
                                "workflow_id": workflow_info.workflow_id,
                                "node_type": node_type,
                                "node_name": node_name,
                                "trigger_type": workflow_info.trigger_type,
                            },
                        )
                        components.append(component)
                        break  # One finding per node

            # Check code nodes for dangerous patterns
            if node_type == "n8n-nodes-base.code":
                code_content = (
                    parameters.get("jsCode", "")
                    or parameters.get("code", "")
                )
                if code_content:
                    for danger_pattern in dangerous_code_patterns:
                        if re.search(danger_pattern, code_content):
                            location = SourceLocation(
                                file_path=str(file_path.resolve()),
                                context_snippet=(
                                    f"Workflow: {workflow_info.workflow_name},"
                                    f" Node: {node_name}"
                                ),
                            )
                            component = AIComponent(
                                name=f"Dangerous Code: {node_name}",
                                type=ComponentType.tool,
                                provider="n8n",
                                location=location,
                                usage_type=UsageType.tool_use,
                                source="n8n",
                                flags=["code_http_tools"],
                                metadata={
                                    "workflow_name": workflow_info.workflow_name,
                                    "workflow_id": workflow_info.workflow_id,
                                    "node_type": node_type,
                                    "node_name": node_name,
                                    "trigger_type": workflow_info.trigger_type,
                                },
                            )
                            components.append(component)
                            break  # One finding per node

    def _node_to_component(
        self,
        node: dict[str, Any],
        file_path: Path,
        workflow_info: N8nWorkflowInfo,
    ) -> AIComponent | None:
        """Convert n8n node to AIComponent.

        Args:
            node: n8n node object
            file_path: Path to workflow file
            workflow_info: Workflow metadata

        Returns:
            AIComponent if successfully mapped, None otherwise
        """
        node_type = node.get("type", "")
        node_name = node.get("name", "")
        parameters = node.get("parameters", {})

        # Map node type to component attributes
        component_info = self._map_node_type(node_type)
        if not component_info:
            return None

        comp_type, usage_type, provider = component_info

        # Extract model name from parameters
        model_name = self._extract_model_name(parameters, node_type)

        # Create location
        location = SourceLocation(
            file_path=str(file_path.resolve()),
            context_snippet=(
                f"Workflow: {workflow_info.workflow_name},"
                f" Node: {node_name}"
            ),
        )

        # Create component
        component = AIComponent(
            name=node_name or node_type,
            type=comp_type,
            provider=provider,
            model_name=model_name,
            location=location,
            usage_type=usage_type,
            source="n8n",
            metadata={
                "workflow_name": workflow_info.workflow_name,
                "workflow_id": workflow_info.workflow_id,
                "node_type": node_type,
                "trigger_type": workflow_info.trigger_type,
            },
        )

        # Check for hardcoded credentials in parameters
        if self._has_hardcoded_credentials(parameters, node.get("credentials", {})):
            component.flags.append("hardcoded_credentials")

        # MCP-specific checks
        if comp_type == ComponentType.mcp_client:
            self._check_mcp_risks(parameters, component)

        return component

    def _map_node_type(
        self, node_type: str
    ) -> tuple[ComponentType, UsageType, str] | None:
        """Map n8n node type to component attributes.

        Args:
            node_type: n8n node type string

        Returns:
            Tuple of (ComponentType, UsageType, provider) or None
        """
        # Agent nodes
        if ".agent" in node_type:
            return (ComponentType.agent_framework, UsageType.agent, "n8n")

        # LLM provider nodes
        if ".lmChatOpenAi" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "OpenAI")
        if ".lmChatAnthropic" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Anthropic")
        if ".lmChatGoogleGemini" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Google")
        if ".lmChatOllama" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Ollama")
        if ".lmChatAzureOpenAi" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Azure OpenAI")
        if ".lmChatMistralCloud" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Mistral")
        if ".lmChatGroq" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Groq")
        if ".lmChatCohere" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "Cohere")
        if ".lmChatHuggingFace" in node_type:
            return (ComponentType.llm_provider, UsageType.completion, "HuggingFace")

        # MCP client
        if ".mcpClientTool" in node_type:
            return (ComponentType.mcp_client, UsageType.tool_use, "MCP")

        # Tool nodes
        if ".toolHttpRequest" in node_type:
            return (ComponentType.tool, UsageType.tool_use, "n8n")
        if ".toolCode" in node_type:
            return (ComponentType.tool, UsageType.tool_use, "n8n")
        if ".toolWorkflow" in node_type:
            return (ComponentType.tool, UsageType.tool_use, "n8n")
        if ".toolCalculator" in node_type:
            return (ComponentType.tool, UsageType.tool_use, "n8n")
        if ".toolWikipedia" in node_type:
            return (ComponentType.tool, UsageType.tool_use, "n8n")

        # Embedding nodes
        if "embedding" in node_type.lower():
            provider = "unknown"
            if "OpenAi" in node_type:
                provider = "OpenAI"
            elif "Azure" in node_type:
                provider = "Azure OpenAI"
            elif "Cohere" in node_type:
                provider = "Cohere"
            elif "HuggingFace" in node_type:
                provider = "HuggingFace"
            elif "GoogleGemini" in node_type:
                provider = "Google"
            elif "Ollama" in node_type:
                provider = "Ollama"
            return (ComponentType.model, UsageType.embedding, provider)

        # Vector store nodes
        if "vectorStore" in node_type:
            provider = "unknown"
            if "Chroma" in node_type:
                provider = "ChromaDB"
            elif "Pinecone" in node_type:
                provider = "Pinecone"
            elif "Qdrant" in node_type:
                provider = "Qdrant"
            elif "Supabase" in node_type:
                provider = "Supabase"
            elif "InMemory" in node_type:
                provider = "in-memory"
            elif "Weaviate" in node_type:
                provider = "Weaviate"
            return (ComponentType.tool, UsageType.embedding, provider)

        # Chain nodes
        if "chain" in node_type.lower():
            return (ComponentType.agent_framework, UsageType.orchestration, "n8n")

        # Memory nodes
        if "memory" in node_type.lower():
            return (ComponentType.tool, UsageType.tool_use, "n8n")

        return None

    def _extract_model_name(
        self, parameters: dict[str, Any], node_type: str
    ) -> str:
        """Extract model name from node parameters.

        Args:
            parameters: Node parameters object
            node_type: Node type string

        Returns:
            Model name string or empty string
        """
        # Common model parameter names
        model_keys = ["model", "modelId", "modelName", "modelVersion"]

        for key in model_keys:
            if key in parameters:
                value = parameters[key]
                if isinstance(value, str):
                    return value

        # Check nested resource parameter (common in n8n)
        if "resource" in parameters and isinstance(parameters["resource"], dict):
            for key in model_keys:
                if key in parameters["resource"]:
                    value = parameters["resource"][key]
                    if isinstance(value, str):
                        return value

        return ""

    def _has_hardcoded_credentials(
        self,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        """Check if node has hardcoded credentials in parameters.

        Args:
            parameters: Node parameters
            credentials: Node credentials references

        Returns:
            True if hardcoded credentials found, False otherwise
        """
        # If credentials are properly referenced via credentials object, that's safe
        # We're looking for API keys/tokens directly in parameters

        # Check for common credential keys in parameters
        credential_keys = [
            "apiKey",
            "api_key",
            "token",
            "accessToken",
            "access_token",
            "secret",
            "secretKey",
            "secret_key",
            "password",
            "authToken",
            "auth_token",
        ]

        # Check parameters for credential keys with non-empty values
        for key in credential_keys:
            if key in parameters:
                value = parameters[key]
                # Check if it's a non-empty string that looks like a credential
                if isinstance(value, str) and value and len(value) > 5:
                    # Exclude common placeholders
                    if value.lower() not in {
                        "your_api_key",
                        "your-api-key",
                        "placeholder",
                        "example",
                    }:
                        return True

        # Check against known API key patterns
        params_str = json.dumps(parameters)
        for pattern, _ in API_KEY_PATTERNS:
            if re.search(pattern, params_str):
                return True

        return False

    def _check_mcp_risks(
        self, parameters: dict[str, Any], component: AIComponent
    ) -> None:
        """Check for MCP-specific security risks.

        Args:
            parameters: Node parameters
            component: Component to add flags to
        """
        # Check all URL-like parameters for non-local servers
        url_keys = ["sseEndpoint", "sseUrl", "serverUrl", "url", "endpoint"]
        for key in url_keys:
            url_value = parameters.get(key, "")
            if url_value and isinstance(url_value, str):
                # Check if it's NOT localhost/127.0.0.1
                if not (
                    "localhost" in url_value.lower()
                    or "127.0.0.1" in url_value
                    or "::1" in url_value
                ):
                    component.flags.append("mcp_unknown_server")
                    break  # Only flag once

    def _apply_workflow_risks(
        self,
        workflow_data: dict[str, Any],
        components: list[AIComponent],
    ) -> None:
        """Apply workflow-level risk patterns to components.

        Args:
            workflow_data: Parsed workflow JSON
            components: List of components to add flags to
        """
        nodes = workflow_data.get("nodes", [])
        connections = workflow_data.get("connections", {})

        # Check for webhook with no auth
        has_insecure_webhook = self._has_insecure_webhook(nodes)
        if has_insecure_webhook:
            # Add flag to all agent components in this workflow
            for component in components:
                if component.type == ComponentType.agent_framework:
                    component.flags.append("webhook_no_auth")

        # Check for agents with dangerous tool combinations
        self._check_agent_tool_risks(nodes, connections, components)

        # Check for agent chains without validation
        self._check_agent_chain_risks(nodes, connections, components)

    def _has_insecure_webhook(self, nodes: list[dict[str, Any]]) -> bool:
        """Check if workflow has webhook trigger with no authentication.

        Args:
            nodes: List of workflow nodes

        Returns:
            True if insecure webhook found, False otherwise
        """
        for node in nodes:
            node_type = node.get("type", "")
            if "webhook" in node_type.lower():
                parameters = node.get("parameters", {})
                auth = parameters.get("authentication")

                # No auth field or explicitly set to "none"
                if auth is None or auth == "none":
                    return True

        return False

    def _check_agent_tool_risks(
        self,
        nodes: list[dict[str, Any]],
        connections: dict[str, Any],
        components: list[AIComponent],
    ) -> None:
        """Check for risky tool combinations connected to agents.

        Args:
            nodes: List of workflow nodes
            connections: Workflow connections
            components: List of components to add flags to
        """
        # Build node name to node mapping
        node_map = {node.get("name", ""): node for node in nodes}

        # Find agent nodes and their connected tools
        for node in nodes:
            if not self._is_agent_node(node.get("type", "")):
                continue

            node_name = node.get("name", "")
            if node_name not in connections:
                continue

            # Get connected node names
            connected_names = self._get_all_connected_nodes(node_name, connections)

            # Check for dangerous tool combinations
            has_code_tool = False
            has_http_tool = False

            for connected_name in connected_names:
                connected_node = node_map.get(connected_name)
                if not connected_node:
                    continue

                conn_type = connected_node.get("type", "")
                if ".toolCode" in conn_type or conn_type == "n8n-nodes-base.code":
                    has_code_tool = True
                if (
                    ".toolHttpRequest" in conn_type
                    or conn_type == "n8n-nodes-base.httpRequest"
                ):
                    has_http_tool = True

            # Flag agent if it has both code and HTTP tools
            if has_code_tool and has_http_tool:
                for component in components:
                    if (
                        component.type == ComponentType.agent_framework
                        and component.name == node_name
                    ):
                        component.flags.append("code_http_tools")

    def _check_agent_chain_risks(
        self,
        nodes: list[dict[str, Any]],
        connections: dict[str, Any],
        components: list[AIComponent],
    ) -> None:
        """Check for agent chains without validation.

        Args:
            nodes: List of workflow nodes
            connections: Workflow connections
            components: List of components to add flags to
        """
        # Build node type map
        node_map = {node.get("name", ""): node for node in nodes}

        # Find executeWorkflow nodes that connect agents
        for node in nodes:
            node_type = node.get("type", "")
            if "executeWorkflow" not in node_type:
                continue

            node_name = node.get("name", "")

            # Check if this node is connected to/from agents
            has_agent_input = False
            has_agent_output = False

            # Check incoming connections
            for source_node, targets in connections.items():
                if isinstance(targets, dict):
                    for conn_type, conn_list in targets.items():
                        if isinstance(conn_list, list):
                            for conn_group in conn_list:
                                if isinstance(conn_group, list):
                                    for conn in conn_group:
                                        if isinstance(conn, dict):
                                            if conn.get("node") == node_name:
                                                source = node_map.get(source_node)
                                                if source and self._is_agent_node(
                                                    source.get("type", "")
                                                ):
                                                    has_agent_input = True

            # Check outgoing connections
            connected_names = self._get_all_connected_nodes(node_name, connections)
            for connected_name in connected_names:
                connected_node = node_map.get(connected_name)
                if connected_node and self._is_agent_node(
                    connected_node.get("type", "")
                ):
                    has_agent_output = True

            # Flag if workflow execution chains agents
            if has_agent_input and has_agent_output:
                # Add flag to agents involved in the chain
                for component in components:
                    if component.type == ComponentType.agent_framework:
                        component.flags.append("agent_chain_no_validation")

    def _get_all_connected_nodes(
        self, node_name: str, connections: dict[str, Any]
    ) -> list[str]:
        """Get all nodes connected to the given node.

        Args:
            node_name: Name of node to check
            connections: Workflow connections

        Returns:
            List of connected node names
        """
        connected: list[str] = []

        if node_name not in connections:
            return connected

        connection_types = connections[node_name]
        if not isinstance(connection_types, dict):
            return connected

        for conn_type, conn_list in connection_types.items():
            if not isinstance(conn_list, list):
                continue

            for conn_group in conn_list:
                if not isinstance(conn_group, list):
                    continue

                for conn in conn_group:
                    if isinstance(conn, dict):
                        target = conn.get("node")
                        if target:
                            connected.append(target)

        return connected

    def _detect_agent_chains(
        self, workflows: dict[str, N8nWorkflowInfo], components: list[AIComponent]
    ) -> None:
        """Detect agent chains across multiple workflows.

        Args:
            workflows: Dictionary of workflow file paths to workflow info
            components: List of all components to add flags to
        """
        # Build workflow name to components mapping
        workflow_components: dict[str, list[AIComponent]] = {}

        for component in components:
            workflow_name = component.metadata.get("workflow_name", "")
            if workflow_name not in workflow_components:
                workflow_components[workflow_name] = []
            workflow_components[workflow_name].append(component)

        # Check each workflow for executeWorkflow nodes pointing to AI workflows
        for workflow_info in workflows.values():
            agent_count = sum(
                1 for comp in workflow_components.get(workflow_info.workflow_name, [])
                if comp.type == ComponentType.agent_framework
            )

            # If workflow has agents and also has agent chains, that's a risk
            if agent_count > 1 and workflow_info.agent_chains:
                # Add flag to agents in multi-agent chains
                for component in workflow_components.get(workflow_info.workflow_name, []):
                    if component.type == ComponentType.agent_framework:
                        if "agent_chain_no_validation" not in component.flags:
                            component.flags.append("multi_agent_no_trust")
