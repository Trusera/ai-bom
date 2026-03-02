"""Tests for Milestone 5: Enhanced Detection Capabilities.

Covers:
- 5a  A2A protocol detection (packages + endpoints)
- 5b  CrewAI flow decorator detection
- 5c  MCP config file parsing
- 5d  AST scanner (imports, decorators, API calls, model strings)
- 5e  Latest model patterns and deprecated model detection
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import pytest

from ai_bom.config import (
    CREWAI_FLOW_PATTERNS,
    DEPRECATED_MODELS,
    KNOWN_AI_PACKAGES,
    KNOWN_MODEL_PATTERNS,
    MCP_CONFIG_FILES,
)
from ai_bom.detectors.endpoint_db import match_endpoint
from ai_bom.detectors.llm_patterns import LLM_PATTERNS
from ai_bom.models import ComponentType, UsageType
from ai_bom.scanners.ast_scanner import ASTScanner
from ai_bom.scanners.network_scanner import NetworkScanner

# ── 5a: A2A Protocol Detection ──────────────────────────────────────────────


class TestA2ADetection:
    """Test A2A package and endpoint detection."""

    def test_a2a_packages_in_known_packages(self):
        assert "a2a" in KNOWN_AI_PACKAGES
        assert "a2a-sdk" in KNOWN_AI_PACKAGES
        provider, usage = KNOWN_AI_PACKAGES["a2a"]
        assert provider == "A2A"
        assert usage == "agent"

    def test_google_adk_packages(self):
        assert "google.adk" in KNOWN_AI_PACKAGES
        assert "google-adk" in KNOWN_AI_PACKAGES
        provider, usage = KNOWN_AI_PACKAGES["google.adk"]
        assert provider == "Google"
        assert usage == "agent"

    def test_a2a_endpoint_pattern(self):
        result = match_endpoint("https://a2a.googleapis.com/v1/agents")
        assert result is not None
        provider, usage = result
        assert provider == "Google A2A"
        assert usage == "agent"

    def test_a2a_endpoint_no_false_positive(self):
        result = match_endpoint("https://example.com/a2a-docs")
        assert result is None


# ── 5b: CrewAI Flow Detection ───────────────────────────────────────────────


class TestCrewAIFlowDetection:
    """Test CrewAI flow decorator detection."""

    def test_crewai_flow_patterns_defined(self):
        assert "@crew" in CREWAI_FLOW_PATTERNS
        assert "@agent" in CREWAI_FLOW_PATTERNS
        assert "@task" in CREWAI_FLOW_PATTERNS
        assert "@flow" in CREWAI_FLOW_PATTERNS
        assert "@tool" in CREWAI_FLOW_PATTERNS
        assert "@start" in CREWAI_FLOW_PATTERNS
        assert "@listen" in CREWAI_FLOW_PATTERNS
        assert "@router" in CREWAI_FLOW_PATTERNS

    def test_crewai_flow_pattern_values(self):
        assert CREWAI_FLOW_PATTERNS["@crew"] == "crew_definition"
        assert CREWAI_FLOW_PATTERNS["@agent"] == "agent_definition"
        assert CREWAI_FLOW_PATTERNS["@task"] == "task_definition"
        assert CREWAI_FLOW_PATTERNS["@flow"] == "flow_definition"
        assert CREWAI_FLOW_PATTERNS["@tool"] == "tool_definition"
        assert CREWAI_FLOW_PATTERNS["@start"] == "flow_start"
        assert CREWAI_FLOW_PATTERNS["@listen"] == "flow_listener"
        assert CREWAI_FLOW_PATTERNS["@router"] == "flow_router"

    def test_crewai_llm_pattern_has_flow_decorators(self):
        crewai_patterns = [p for p in LLM_PATTERNS if p.sdk_name == "CrewAI"]
        assert len(crewai_patterns) == 1
        crewai = crewai_patterns[0]
        assert any("@flow" in p for p in crewai.usage_patterns)
        assert any("@crew" in p for p in crewai.usage_patterns)
        assert any("@agent" in p for p in crewai.usage_patterns)
        assert any("@task" in p for p in crewai.usage_patterns)
        assert any("@tool" in p for p in crewai.usage_patterns)
        assert any("@start" in p for p in crewai.usage_patterns)
        assert any("@listen" in p for p in crewai.usage_patterns)
        assert any("@router" in p for p in crewai.usage_patterns)

    def test_crewai_flow_import_pattern(self):
        crewai_patterns = [p for p in LLM_PATTERNS if p.sdk_name == "CrewAI"]
        crewai = crewai_patterns[0]
        # Should detect 'from crewai.flow' import
        assert any(re.search(p, "from crewai.flow import Flow") for p in crewai.import_patterns)


# ── 5b-ext: CrewAI Flow Decorators (Issue #40) ─────────────────────────────


class TestCrewAIFlowDecorators:
    """Test CrewAI Flow decorator detection, class inheritance, and relationships."""

    def _scan_code(self, code: str) -> list:
        """Helper: parse *code* with ASTScanner and return detected components."""
        import ast

        scanner = ASTScanner()
        scanner.enabled = True
        source = textwrap.dedent(code)
        tree = ast.parse(source)
        return scanner._analyse_tree(tree, Path("test.py"), source)

    # -- decorator detection ------------------------------------------

    def test_start_decorator_detected(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, start

            class F(Flow):
                @start()
                def begin(self):
                    pass
        """)
        start_comps = [c for c in comps if c.metadata.get("pattern_type") == "flow_start"]
        assert len(start_comps) == 1
        assert start_comps[0].usage_type == UsageType.orchestration
        assert start_comps[0].metadata["decorator"] == "start"

    def test_listen_decorator_with_name_ref(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, start, listen

            class F(Flow):
                @start()
                def begin(self):
                    pass
                @listen(begin)
                def process(self, data):
                    pass
        """)
        listen_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        ]
        assert len(listen_comps) == 1
        assert listen_comps[0].metadata["listens_to"] == "begin"
        assert listen_comps[0].usage_type == UsageType.orchestration

    def test_router_decorator_with_name_ref(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, start, router

            class F(Flow):
                @start()
                def begin(self):
                    pass
                @router(begin)
                def route(self, data):
                    pass
        """)
        router_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_router"
        ]
        assert len(router_comps) == 1
        assert router_comps[0].metadata["routes_from"] == "begin"
        assert router_comps[0].usage_type == UsageType.orchestration

    # -- relationship edge cases --------------------------------------

    def test_listen_attribute_ref(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, listen

            class F(Flow):
                @listen(self.begin)
                def process(self, data):
                    pass
        """)
        listen_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        ]
        assert len(listen_comps) == 1
        assert listen_comps[0].metadata["listens_to"] == "self.begin"

    def test_listen_string_ref(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, listen

            class F(Flow):
                @listen("begin")
                def process(self, data):
                    pass
        """)
        listen_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        ]
        assert len(listen_comps) == 1
        assert listen_comps[0].metadata["listens_to"] == "begin"

    def test_listen_multiple_args(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, listen

            class F(Flow):
                @listen(step_a, step_b)
                def combine(self, data):
                    pass
        """)
        listen_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        ]
        assert len(listen_comps) == 1
        assert listen_comps[0].metadata["listens_to"] == ["step_a", "step_b"]

    def test_listen_no_args(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow, listen

            class F(Flow):
                @listen()
                def process(self, data):
                    pass
        """)
        listen_comps = [
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        ]
        assert len(listen_comps) == 1
        assert "listens_to" not in listen_comps[0].metadata

    # -- flow class inheritance ---------------------------------------

    def test_flow_class_direct(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow

            class MyFlow(Flow):
                pass
        """)
        flow_cls = [c for c in comps if c.metadata.get("pattern_type") == "flow_class"]
        assert len(flow_cls) == 1
        assert flow_cls[0].name == "CrewAI Flow: MyFlow"
        assert flow_cls[0].metadata["base_class"] == "Flow"
        assert flow_cls[0].usage_type == UsageType.orchestration

    def test_flow_class_alias(self):
        comps = self._scan_code("""\
            from crewai.flow import Flow as BaseFlow

            class MyFlow(BaseFlow):
                pass
        """)
        flow_cls = [c for c in comps if c.metadata.get("pattern_type") == "flow_class"]
        assert len(flow_cls) == 1
        assert flow_cls[0].metadata["base_class"] == "BaseFlow"

    def test_flow_class_attribute_chain(self):
        comps = self._scan_code("""\
            import crewai.flow

            class MyFlow(crewai.flow.Flow):
                pass
        """)
        flow_cls = [c for c in comps if c.metadata.get("pattern_type") == "flow_class"]
        assert len(flow_cls) == 1
        assert flow_cls[0].metadata["base_class"] == "crewai.flow.Flow"

    def test_non_flow_class_ignored(self):
        comps = self._scan_code("""\
            class NotAFlow(SomeOtherBase):
                pass
        """)
        flow_cls = [c for c in comps if c.metadata.get("pattern_type") == "flow_class"]
        assert len(flow_cls) == 0

    # -- usage type ---------------------------------------------------

    def test_original_decorators_keep_agent_usage_type(self):
        comps = self._scan_code("""\
            from crewai import crew, agent, task

            @crew
            def my_crew():
                pass

            @agent
            def my_agent():
                pass

            @task
            def my_task():
                pass
        """)
        for c in comps:
            if c.metadata.get("decorator") in ("crew", "agent", "task"):
                assert c.usage_type == UsageType.agent

    # -- integration: fixture file ------------------------------------

    def test_full_fixture_scan(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "sample_crew_flow.py"
        scanner = ASTScanner()
        scanner.enabled = True
        comps = scanner.scan(fixture)

        pattern_types = {c.metadata.get("pattern_type") for c in comps}
        assert "flow_class" in pattern_types
        assert "flow_start" in pattern_types
        assert "flow_listener" in pattern_types
        assert "flow_router" in pattern_types

        flow_comps = [
            c for c in comps if c.metadata.get("pattern_type", "").startswith("flow_")
        ]
        assert len(flow_comps) >= 4  # class + start + listen + router
        for c in flow_comps:
            assert c.usage_type == UsageType.orchestration
            assert c.type == ComponentType.agent_framework
            assert c.provider == "CrewAI"

        listen_comp = next(
            c for c in comps if c.metadata.get("pattern_type") == "flow_listener"
        )
        assert listen_comp.metadata["listens_to"] == "begin"

        router_comp = next(
            c for c in comps if c.metadata.get("pattern_type") == "flow_router"
        )
        assert router_comp.metadata["routes_from"] == "process"


# ── 5c: MCP Config File Detection ──────────────────────────────────────────


class TestMCPConfigDetection:
    """Test MCP config file parsing via NetworkScanner."""

    def test_mcp_config_files_defined(self):
        assert "mcp.json" in MCP_CONFIG_FILES
        assert ".mcp.json" in MCP_CONFIG_FILES
        assert "mcp-config.json" in MCP_CONFIG_FILES
        assert "claude_desktop_config.json" in MCP_CONFIG_FILES

    def test_parse_mcp_config_servers(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
                "remote-api": {
                    "url": "https://remote-mcp.example.com/sse",
                },
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config))

        scanner = NetworkScanner()
        components = scanner.scan(config_file)

        mcp_components = [c for c in components if c.type.value == "mcp_server"]
        assert len(mcp_components) == 2

        names = {c.name for c in mcp_components}
        assert "MCP Server: filesystem" in names
        assert "MCP Server: remote-api" in names

    def test_mcp_remote_server_flagged(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "remote": {
                    "url": "https://external-server.example.com/mcp",
                },
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config))

        scanner = NetworkScanner()
        components = scanner.scan(config_file)

        mcp_components = [c for c in components if c.type.value == "mcp_server"]
        assert len(mcp_components) == 1
        assert "mcp_unknown_server" in mcp_components[0].flags

    def test_mcp_localhost_not_flagged(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "local": {
                    "url": "http://localhost:3000/mcp",
                },
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config))

        scanner = NetworkScanner()
        components = scanner.scan(config_file)

        mcp_components = [c for c in components if c.type.value == "mcp_server"]
        assert len(mcp_components) == 1
        assert "mcp_unknown_server" not in mcp_components[0].flags

    def test_mcp_invalid_json_skipped(self, tmp_path: Path):
        config_file = tmp_path / "mcp.json"
        config_file.write_text("not valid json {{{")

        scanner = NetworkScanner()
        components = scanner.scan(config_file)
        mcp_components = [c for c in components if c.type.value == "mcp_server"]
        assert len(mcp_components) == 0

    def test_mcp_config_dir_scan(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "test-server": {"command": "node", "args": ["server.js"]},
            }
        }
        config_file = tmp_path / ".mcp.json"
        config_file.write_text(json.dumps(config))

        scanner = NetworkScanner()
        components = scanner.scan(tmp_path)
        mcp_components = [c for c in components if c.type.value == "mcp_server"]
        assert len(mcp_components) == 1
        assert mcp_components[0].name == "MCP Server: test-server"


# ── 5d: AST Scanner ────────────────────────────────────────────────────────


class TestASTScanner:
    """Test AST-based Python scanner."""

    def test_disabled_by_default(self, tmp_path: Path):
        scanner = ASTScanner()
        assert scanner.enabled is False
        assert scanner.supports(tmp_path) is False

    def test_enabled_supports_directory(self, tmp_path: Path):
        scanner = ASTScanner()
        scanner.enabled = True
        assert scanner.supports(tmp_path) is True

    def test_enabled_supports_py_file(self, tmp_path: Path):
        py_file = tmp_path / "test.py"
        py_file.write_text("# empty")
        scanner = ASTScanner()
        scanner.enabled = True
        assert scanner.supports(py_file) is True

    def test_does_not_support_non_py(self, tmp_path: Path):
        js_file = tmp_path / "test.js"
        js_file.write_text("// empty")
        scanner = ASTScanner()
        scanner.enabled = True
        assert scanner.supports(js_file) is False

    def test_detect_openai_import(self, tmp_path: Path):
        code = textwrap.dedent("""\
            import openai
            client = openai.OpenAI()
        """)
        py_file = tmp_path / "app.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        import_components = [c for c in components if "import" in c.name.lower()]
        assert len(import_components) >= 1
        assert import_components[0].provider == "OpenAI"
        assert import_components[0].source == "ast"

    def test_detect_anthropic_import(self, tmp_path: Path):
        code = textwrap.dedent("""\
            from anthropic import Anthropic
        """)
        py_file = tmp_path / "app.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        import_components = [c for c in components if "import" in c.name.lower()]
        assert len(import_components) >= 1
        assert import_components[0].provider == "Anthropic"

    def test_detect_crewai_decorator(self, tmp_path: Path):
        code = textwrap.dedent("""\
            from crewai import agent, task

            @agent
            def my_agent():
                pass

            @task
            def my_task():
                pass
        """)
        py_file = tmp_path / "crew.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        # Should detect @agent and @task decorators
        agent_decs = [c for c in components if c.metadata.get("decorator") == "agent"]
        task_decs = [c for c in components if c.metadata.get("decorator") == "task"]
        assert len(agent_decs) >= 1
        assert len(task_decs) >= 1

    def test_detect_flow_decorator(self, tmp_path: Path):
        code = textwrap.dedent("""\
            from crewai.flow import Flow

            @flow
            def my_flow():
                pass
        """)
        py_file = tmp_path / "flows.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        flow_components = [c for c in components if c.metadata.get("decorator") == "flow"]
        assert len(flow_components) >= 1

    def test_detect_model_string_literal(self, tmp_path: Path):
        code = textwrap.dedent("""\
            model = "gpt-4o"
        """)
        py_file = tmp_path / "config.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        model_components = [c for c in components if c.type.value == "model"]
        assert len(model_components) >= 1
        assert model_components[0].model_name == "gpt-4o"
        assert model_components[0].provider == "OpenAI"

    def test_detect_api_call(self, tmp_path: Path):
        code = textwrap.dedent("""\
            import openai
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}]
            )
        """)
        py_file = tmp_path / "chat.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(py_file)

        api_components = [c for c in components if "API call" in c.name]
        assert len(api_components) >= 1

    def test_syntax_error_skipped(self, tmp_path: Path):
        code = "def broken(:\n  pass"
        py_file = tmp_path / "broken.py"
        py_file.write_text(code)

        scanner = ASTScanner()
        scanner.enabled = True
        # Should not raise
        components = scanner.scan(py_file)
        assert isinstance(components, list)

    def test_scan_directory(self, tmp_path: Path):
        code1 = "import openai\n"
        code2 = "import anthropic\n"
        (tmp_path / "a.py").write_text(code1)
        (tmp_path / "b.py").write_text(code2)

        scanner = ASTScanner()
        scanner.enabled = True
        components = scanner.scan(tmp_path)

        providers = {c.provider for c in components}
        assert "OpenAI" in providers
        assert "Anthropic" in providers


# ── 5e: Latest Model Patterns ──────────────────────────────────────────────


class TestLatestModelPatterns:
    """Test new model pattern matching."""

    @pytest.mark.parametrize(
        "model_name,expected_provider",
        [
            ("gpt-4.5-preview", "OpenAI"),
            ("o1", "OpenAI"),
            ("o1-mini", "OpenAI"),
            ("o3-mini", "OpenAI"),
            ("claude-4-sonnet", "Anthropic"),
            ("claude-4.5-sonnet", "Anthropic"),
            ("claude-sonnet-4-20250514", "Anthropic"),
            ("claude-opus-4-20250514", "Anthropic"),
            ("claude-haiku-4-20250514", "Anthropic"),
            ("gemini-2.0-flash", "Google"),
            ("gemini-2.5-pro", "Google"),
            ("llama-4-scout", "Meta"),
            ("deepseek-chat", "DeepSeek"),
            ("deepseek-coder", "DeepSeek"),
            ("deepseek-r1", "DeepSeek"),
        ],
    )
    def test_model_pattern_matches(self, model_name: str, expected_provider: str):
        matched = False
        for pattern, provider in KNOWN_MODEL_PATTERNS:
            if re.fullmatch(pattern, model_name):
                assert provider == expected_provider, (
                    f"{model_name} matched provider={provider}, expected={expected_provider}"
                )
                matched = True
                break
        assert matched, f"Model '{model_name}' did not match any pattern"

    def test_deepseek_model_pattern(self):
        """DeepSeek detection is via model patterns and API keys, not a fake package name."""
        from ai_bom.config import KNOWN_MODEL_PATTERNS

        matched = any(
            pattern.search("deepseek-coder") and provider == "DeepSeek"
            for pattern, provider in KNOWN_MODEL_PATTERNS
        )
        assert matched, "DeepSeek model pattern should match 'deepseek-coder'"


class TestDeprecatedModels:
    """Test deprecated model detection."""

    @pytest.mark.parametrize(
        "model",
        [
            "gpt-4-0314",
            "gpt-4-0613",
            "gpt-4-32k-0314",
            "gpt-4-32k-0613",
            "claude-2.1",
            "claude-3-haiku-20240307",
            # Existing deprecated
            "gpt-3.5-turbo",
            "claude-instant-1",
            "claude-2.0",
        ],
    )
    def test_model_is_deprecated(self, model: str):
        assert model in DEPRECATED_MODELS, f"{model} should be in DEPRECATED_MODELS"

    def test_non_deprecated_model_not_in_set(self):
        assert "gpt-4o" not in DEPRECATED_MODELS
        assert "claude-sonnet-4-20250514" not in DEPRECATED_MODELS
