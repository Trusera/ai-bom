"""Network scanner for detecting AI endpoints and API keys in configuration files.

This scanner examines environment files and configuration files to detect:
- AI service endpoints (API URLs)
- Hardcoded API keys
- Environment variable patterns for AI services
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Set, Tuple

from ai_bom.detectors.endpoint_db import detect_api_key, match_endpoint
from ai_bom.models import (
    AIComponent,
    ComponentType,
    RiskAssessment,
    Severity,
    SourceLocation,
    UsageType,
)
from ai_bom.scanners.base import BaseScanner

# AI environment variable patterns
AI_ENV_VAR_PATTERNS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "COHERE_API_KEY",
    "MISTRAL_API_KEY",
    "GOOGLE_AI_KEY",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_API_KEY",
    "TOGETHER_API_KEY",
    "REPLICATE_API_TOKEN",
    "OLLAMA_HOST",
    "GROQ_API_KEY",
    "AWS_BEDROCK",
    "VERTEX_AI",
    "XAI_API_KEY",
]

# Mapping of env var names to providers
ENV_VAR_TO_PROVIDER = {
    "OPENAI_API_KEY": "OpenAI",
    "ANTHROPIC_API_KEY": "Anthropic",
    "HF_TOKEN": "HuggingFace",
    "HUGGINGFACE_TOKEN": "HuggingFace",
    "COHERE_API_KEY": "Cohere",
    "MISTRAL_API_KEY": "Mistral",
    "GOOGLE_AI_KEY": "Google",
    "GOOGLE_API_KEY": "Google",
    "AZURE_OPENAI_KEY": "Azure OpenAI",
    "AZURE_OPENAI_API_KEY": "Azure OpenAI",
    "TOGETHER_API_KEY": "Together",
    "REPLICATE_API_TOKEN": "Replicate",
    "OLLAMA_HOST": "Ollama",
    "GROQ_API_KEY": "Groq",
    "AWS_BEDROCK": "AWS Bedrock",
    "VERTEX_AI": "Google Vertex AI",
    "XAI_API_KEY": "xAI",
}

# Files to skip
SKIP_CONFIG_FILES = {
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.build.json",
    "jest.config.json",
    "eslint.config.json",
    "webpack.config.json",
    "babel.config.json",
}


class NetworkScanner(BaseScanner):
    """Scan .env files and configuration files for AI endpoints and API keys.

    Detects:
    - Environment variables for AI services
    - Hardcoded API keys in config files
    - AI service endpoint URLs
    """

    name = "network"
    description = "Scan .env files for AI endpoints & keys"

    def supports(self, path: Path) -> bool:
        """Check if this scanner should run on the given path.

        Args:
            path: Directory or file path to check

        Returns:
            True if path is a directory or a .env/.config file
        """
        if path.is_dir():
            return True

        filename = path.name.lower()

        # Check for .env files
        if filename.startswith(".env"):
            return True

        # Check for config file extensions
        if path.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}:
            return True

        return False

    def scan(self, path: Path) -> list[AIComponent]:
        """Scan path for AI endpoints and API keys in config files.

        Args:
            path: Directory or file to scan

        Returns:
            List of detected AI components
        """
        components: list[AIComponent] = []

        # Track seen (provider, file_path) pairs to avoid duplicates
        seen_endpoints: Set[Tuple[str, str]] = set()

        # Collect files to scan
        files_to_scan: list[Path] = []

        if path.is_file():
            files_to_scan.append(path)
        else:
            # Find .env files
            for file_path in self.iter_files(path):
                filename = file_path.name.lower()

                # Match .env files
                if self._is_env_file(filename):
                    files_to_scan.append(file_path)
                # Match config files (but skip node-related configs)
                elif self._is_config_file(file_path) and filename not in SKIP_CONFIG_FILES:
                    files_to_scan.append(file_path)

        # Scan each file
        for file_path in files_to_scan:
            try:
                components.extend(
                    self._scan_file(file_path, seen_endpoints)
                )
            except Exception:
                # Skip files that can't be read or parsed
                continue

        return components

    def _is_env_file(self, filename: str) -> bool:
        """Check if filename matches .env patterns.

        Args:
            filename: Filename to check (lowercase)

        Returns:
            True if filename is an .env file variant
        """
        env_patterns = [
            ".env",
            ".env.local",
            ".env.production",
            ".env.development",
            ".env.example",
            ".env.sample",
            ".env.test",
            ".env.staging",
        ]

        # Exact matches
        if filename in env_patterns:
            return True

        # Pattern like .env.* but not .envrc
        if filename.startswith(".env.") and len(filename) > 5:
            return True

        return False

    def _is_config_file(self, file_path: Path) -> bool:
        """Check if file is a config file we should scan.

        Args:
            file_path: Path to check

        Returns:
            True if file is a scannable config file
        """
        return file_path.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}

    def _scan_file(
        self,
        file_path: Path,
        seen_endpoints: Set[Tuple[str, str]]
    ) -> list[AIComponent]:
        """Scan a single file for AI endpoints and API keys.

        Args:
            file_path: Path to file to scan
            seen_endpoints: Set of (provider, file_path) tuples already seen

        Returns:
            List of detected AI components from this file
        """
        components: list[AIComponent] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            # Skip files that can't be read
            return components

        lines = content.splitlines()
        is_env_file = self._is_env_file(file_path.name.lower())

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            # For .env files, parse KEY=VALUE
            if is_env_file:
                components.extend(
                    self._scan_env_line(file_path, line_num, line, seen_endpoints)
                )

            # For all files, check for endpoints
            components.extend(
                self._scan_line_for_endpoints(file_path, line_num, line, seen_endpoints)
            )

            # For all files, check for hardcoded API keys
            components.extend(
                self._scan_line_for_api_keys(file_path, line_num, line)
            )

        return components

    def _scan_env_line(
        self,
        file_path: Path,
        line_num: int,
        line: str,
        seen_endpoints: Set[Tuple[str, str]]
    ) -> list[AIComponent]:
        """Scan an .env file line for AI environment variables.

        Args:
            file_path: Path to the .env file
            line_num: Line number
            line: Line content
            seen_endpoints: Set of seen endpoints

        Returns:
            List of components found
        """
        components: list[AIComponent] = []

        # Parse KEY=VALUE (handle quotes and spaces)
        match = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
        if not match:
            return components

        key, value = match.groups()
        value = value.strip().strip('"').strip("'")

        # Check if key matches AI env var patterns
        provider = self._get_provider_from_env_var(key)
        if not provider:
            return components

        # Dedup check
        dedup_key = (provider, str(file_path))
        if dedup_key in seen_endpoints:
            return components
        seen_endpoints.add(dedup_key)

        # Check if value looks like a hardcoded key
        has_hardcoded_key = self._is_hardcoded_value(value)

        # Create component
        flags = []
        risk_factors = []
        risk_score = 10

        if has_hardcoded_key:
            flags.append("hardcoded_api_key")
            risk_factors.append("Hardcoded API key in configuration file")
            risk_score = 30

        component = AIComponent(
            name=f"{provider} Endpoint",
            type=ComponentType.endpoint,
            provider=provider,
            location=SourceLocation(
                file_path=str(file_path),
                line_number=line_num,
                context_snippet=line.strip()[:100],
            ),
            usage_type=UsageType.completion,
            risk=RiskAssessment(
                score=risk_score,
                severity=self._calculate_severity(risk_score),
                factors=risk_factors,
            ),
            flags=flags,
            source="network",
            metadata={"env_var": key, "has_value": bool(value)},
        )
        components.append(component)

        return components

    def _scan_line_for_endpoints(
        self,
        file_path: Path,
        line_num: int,
        line: str,
        seen_endpoints: Set[Tuple[str, str]]
    ) -> list[AIComponent]:
        """Scan a line for AI endpoint URLs.

        Args:
            file_path: Path to file
            line_num: Line number
            line: Line content
            seen_endpoints: Set of seen endpoints

        Returns:
            List of components found
        """
        components: list[AIComponent] = []

        # Check against known endpoints
        result = match_endpoint(line)
        if not result:
            return components

        provider, usage_type = result

        # Dedup check
        dedup_key = (provider, str(file_path))
        if dedup_key in seen_endpoints:
            return components
        seen_endpoints.add(dedup_key)

        # Map usage_type string to UsageType enum
        usage_type_enum = self._map_usage_type(usage_type)

        component = AIComponent(
            name=f"{provider} Endpoint",
            type=ComponentType.endpoint,
            provider=provider,
            location=SourceLocation(
                file_path=str(file_path),
                line_number=line_num,
                context_snippet=line.strip()[:100],
            ),
            usage_type=usage_type_enum,
            risk=RiskAssessment(
                score=10,
                severity=Severity.low,
                factors=["AI endpoint configured in file"],
            ),
            source="network",
        )
        components.append(component)

        return components

    def _scan_line_for_api_keys(
        self,
        file_path: Path,
        line_num: int,
        line: str
    ) -> list[AIComponent]:
        """Scan a line for hardcoded API keys.

        Args:
            file_path: Path to file
            line_num: Line number
            line: Line content

        Returns:
            List of components found
        """
        components: list[AIComponent] = []

        # Detect API keys
        api_keys = detect_api_key(line)
        if not api_keys:
            return components

        for masked_key, provider, pattern in api_keys:
            component = AIComponent(
                name=f"{provider} API Key",
                type=ComponentType.endpoint,
                provider=provider,
                location=SourceLocation(
                    file_path=str(file_path),
                    line_number=line_num,
                    context_snippet=line.strip()[:100],
                ),
                usage_type=UsageType.completion,
                risk=RiskAssessment(
                    score=30,
                    severity=Severity.critical,
                    factors=["Hardcoded API key detected in file"],
                ),
                flags=["hardcoded_api_key"],
                source="network",
                metadata={"masked_key": masked_key, "pattern": pattern},
            )
            components.append(component)

        return components

    def _get_provider_from_env_var(self, key: str) -> str | None:
        """Get provider name from environment variable key.

        Args:
            key: Environment variable name

        Returns:
            Provider name or None if not an AI env var
        """
        # Exact match
        if key in ENV_VAR_TO_PROVIDER:
            return ENV_VAR_TO_PROVIDER[key]

        # Check if key contains _API_KEY with known provider prefix
        if "_API_KEY" in key:
            key_lower = key.lower()
            provider_patterns = [
                ("openai", "OpenAI"),
                ("anthropic", "Anthropic"),
                ("cohere", "Cohere"),
                ("mistral", "Mistral"),
                ("google", "Google"),
                ("azure", "Azure OpenAI"),
                ("huggingface", "HuggingFace"),
                ("replicate", "Replicate"),
                ("together", "Together"),
                ("groq", "Groq"),
                ("xai", "xAI"),
            ]
            for pattern, provider in provider_patterns:
                if pattern in key_lower:
                    return provider

        return None

    def _is_hardcoded_value(self, value: str) -> bool:
        """Check if a value looks like a hardcoded API key (not a reference).

        Args:
            value: Value from env var

        Returns:
            True if value appears to be a hardcoded key
        """
        if not value:
            return False

        # Skip references like ${VAR_NAME}
        if re.match(r'^\$\{[A-Z_][A-Z0-9_]*\}$', value):
            return False

        # Skip placeholder values
        placeholder_indicators = [
            "your",
            "demo",
            "test",
            "example",
            "xxx",
            "placeholder",
            "changeme",
        ]
        value_lower = value.lower()
        if any(indicator in value_lower for indicator in placeholder_indicators):
            return False

        # Check if it matches API key patterns
        api_keys = detect_api_key(value)
        return len(api_keys) > 0

    def _map_usage_type(self, usage_type: str) -> UsageType:
        """Map usage type string to UsageType enum.

        Args:
            usage_type: Usage type string from config

        Returns:
            UsageType enum value
        """
        mapping = {
            "completion": UsageType.completion,
            "embedding": UsageType.embedding,
            "image_gen": UsageType.image_gen,
            "speech": UsageType.speech,
            "agent": UsageType.agent,
            "tool_use": UsageType.tool_use,
            "orchestration": UsageType.orchestration,
        }
        return mapping.get(usage_type, UsageType.unknown)

    def _calculate_severity(self, risk_score: int) -> Severity:
        """Calculate severity from risk score.

        Args:
            risk_score: Risk score (0-100)

        Returns:
            Severity level
        """
        if risk_score >= 25:
            return Severity.critical
        elif risk_score >= 15:
            return Severity.high
        elif risk_score >= 10:
            return Severity.medium
        else:
            return Severity.low
