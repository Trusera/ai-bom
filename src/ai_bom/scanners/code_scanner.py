"""Source code scanner for AI SDK imports and usage detection.

This scanner performs two-phase analysis:
1. Dependency file scanning to identify declared AI packages
2. Source code scanning to detect SDK usage, model references, and API keys

The scanner identifies shadow AI (undeclared usage), deprecated models,
unpinned models, and hardcoded credentials.
"""

from __future__ import annotations

import re
from pathlib import Path

from ai_bom.config import (
    DEPRECATED_MODELS,
    KNOWN_AI_PACKAGES,
    SCANNABLE_EXTENSIONS,
)
from ai_bom.detectors.endpoint_db import detect_api_key
from ai_bom.detectors.llm_patterns import LLM_PATTERNS, get_all_dep_names
from ai_bom.models import AIComponent, ComponentType, SourceLocation, UsageType
from ai_bom.scanners.base import BaseScanner


class CodeScanner(BaseScanner):
    """Scan source code for AI SDK imports and usage.

    Detects:
    - AI SDK imports and usage patterns
    - Model names and version pinning
    - Hardcoded API keys
    - Shadow AI (usage without dependency declaration)
    - Deprecated models
    """

    name = "code"
    description = "Scan source code for AI SDK imports & usage"

    def supports(self, path: Path) -> bool:
        """Check if path is scannable source code.

        Args:
            path: Directory or file path to check

        Returns:
            True if path is a directory or a file with scannable extension
        """
        if path.is_dir():
            return True

        # Check if file extension is in scannable code extensions
        file_ext = path.suffix.lower()
        if file_ext in SCANNABLE_EXTENSIONS["code"]:
            return True

        # Also support dependency files
        if path.name in SCANNABLE_EXTENSIONS["deps"]:
            return True

        return False

    def scan(self, path: Path) -> list[AIComponent]:
        """Scan path for AI components using two-phase analysis.

        Phase A: Dependency file scan to build declared_deps set
        Phase B: Source code scan to detect usage and check for shadow AI

        Args:
            path: Directory or file path to scan

        Returns:
            List of detected AI components with risk flags
        """
        components: list[AIComponent] = []

        # Track which files/SDKs we've already created components for
        # to avoid duplicates: key = (sdk_name, file_path)
        seen_components: set[tuple[str, str]] = set()

        # Handle single file scanning
        scan_dir = path if path.is_dir() else path.parent

        # Phase A: Dependency file scan
        declared_deps = self._scan_dependency_files(scan_dir)

        # If single file is a dep file, also scan it directly
        if path.is_file() and path.name in SCANNABLE_EXTENSIONS["deps"]:
            declared_deps.update(self._scan_single_dep_file(path))

        # Create components for declared dependencies
        for dep_name in declared_deps:
            # Look up provider and usage type
            provider, usage_type_str = KNOWN_AI_PACKAGES.get(
                dep_name, ("Unknown", "unknown")
            )

            # Map usage_type string to enum
            usage_type = self._map_usage_type(usage_type_str)

            # Determine component type based on provider/usage
            component_type = self._determine_component_type(provider, usage_type_str)

            component = AIComponent(
                name=dep_name,
                type=component_type,
                provider=provider,
                usage_type=usage_type,
                location=SourceLocation(
                    file_path="dependency files",
                    line_number=None,
                    context_snippet="",
                ),
                source="code",
            )
            components.append(component)

        # Phase B: Source code scan
        if path.is_file() and path.suffix in SCANNABLE_EXTENSIONS["code"]:
            # Single file mode: scan just this file
            source_components = self._scan_single_source_file(
                path, declared_deps, seen_components
            )
        else:
            source_components = self._scan_source_files(
                scan_dir, declared_deps, seen_components
            )
        components.extend(source_components)

        return components

    def _scan_dependency_files(self, path: Path) -> set[str]:
        """Scan dependency files to build set of declared AI packages.

        Args:
            path: Root path to scan

        Returns:
            Set of declared AI package names
        """
        declared_deps: set[str] = set()
        all_known_ai_deps = get_all_dep_names() | set(KNOWN_AI_PACKAGES.keys())

        # Find all dependency files
        dep_files = self.iter_files(path, filenames=SCANNABLE_EXTENSIONS["deps"])

        for dep_file in dep_files:
            filename = dep_file.name.lower()

            try:
                content = dep_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                # Skip unreadable files
                continue

            # Parse based on file type
            if filename == "requirements.txt" or filename == "pipfile":
                declared_deps.update(
                    self._parse_requirements_format(content, all_known_ai_deps)
                )
            elif filename == "pyproject.toml":
                declared_deps.update(
                    self._parse_pyproject_toml(content, all_known_ai_deps)
                )
            elif filename == "package.json":
                declared_deps.update(
                    self._parse_package_json(content, all_known_ai_deps)
                )

        return declared_deps

    def _scan_single_dep_file(self, path: Path) -> set[str]:
        """Scan a single dependency file."""
        all_known_ai_deps = get_all_dep_names() | set(KNOWN_AI_PACKAGES.keys())
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return set()
        filename = path.name.lower()
        if filename == "requirements.txt" or filename == "pipfile":
            return self._parse_requirements_format(content, all_known_ai_deps)
        elif filename == "pyproject.toml":
            return self._parse_pyproject_toml(content, all_known_ai_deps)
        elif filename == "package.json":
            return self._parse_package_json(content, all_known_ai_deps)
        return set()

    def _scan_single_source_file(
        self,
        path: Path,
        declared_deps: set[str],
        seen_components: set[tuple[str, str]],
    ) -> list[AIComponent]:
        """Scan a single source file for AI SDK usage."""
        components: list[AIComponent] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return components
        lines = content.splitlines()
        file_seen_sdks: set[str] = set()
        for line_num, line in enumerate(lines, start=1):
            api_key_results = detect_api_key(line)
            for masked_key, provider, pattern in api_key_results:
                component = AIComponent(
                    name=f"{provider} API Key",
                    type=ComponentType.llm_provider,
                    provider=provider,
                    usage_type=UsageType.unknown,
                    location=SourceLocation(
                        file_path=str(path),
                        line_number=line_num,
                        context_snippet=line.strip()[:200],
                    ),
                    flags=["hardcoded_api_key"],
                    source="code",
                )
                components.append(component)
            for pat in LLM_PATTERNS:
                import_matched = any(
                    re.search(ip, line) for ip in pat.import_patterns
                )
                usage_matched = any(
                    re.search(up, line) for up in pat.usage_patterns
                )
                if import_matched or usage_matched:
                    if pat.sdk_name in file_seen_sdks:
                        continue
                    file_seen_sdks.add(pat.sdk_name)
                    is_shadow_ai = not self._is_declared(pat.dep_names, declared_deps)
                    model_name = ""
                    flags: list[str] = []
                    if pat.model_extraction and usage_matched:
                        model_match = re.search(pat.model_extraction, line)
                        if model_match:
                            model_name = model_match.group(1)
                            if model_name in DEPRECATED_MODELS:
                                flags.append("deprecated_model")
                            if not self._is_model_pinned(model_name):
                                flags.append("unpinned_model")
                    if is_shadow_ai:
                        flags.append("shadow_ai")
                    component = AIComponent(
                        name=pat.sdk_name,
                        type=pat.component_type,
                        provider=pat.provider,
                        model_name=model_name,
                        usage_type=pat.usage_type,
                        location=SourceLocation(
                            file_path=str(path),
                            line_number=line_num,
                            context_snippet=line.strip()[:200],
                        ),
                        flags=flags,
                        source="code",
                    )
                    components.append(component)
        return components

    def _parse_requirements_format(
        self, content: str, known_deps: set[str]
    ) -> set[str]:
        """Parse requirements.txt or Pipfile format.

        Format: package==version or package>=version or just package

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Extract package name (before any version specifier)
            # Split on common version specifiers
            package_name = re.split(r"[=<>!~\[\s]", line)[0].strip()

            # Normalize package name (replace _ with -)
            normalized = package_name.replace("_", "-").lower()

            # Check if it's a known AI package (try both forms)
            if package_name in known_deps or normalized in known_deps:
                found.add(package_name)

        return found

    def _parse_pyproject_toml(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse pyproject.toml dependencies section.

        Looks for dependencies = [ ... ] or tool.poetry.dependencies

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Simple regex-based parsing (good enough for most cases)
        # Match lines like: "openai>=1.0" or "openai" inside dependencies array
        dep_pattern = r'["\']([a-zA-Z0-9_-]+)(?:[>=<\[]|["\'])'

        # Check if we're in a dependencies section
        in_deps_section = False

        for line in content.splitlines():
            line = line.strip()

            # Detect dependencies section start
            if "dependencies" in line and ("[" in line or "=" in line):
                in_deps_section = True

            # Exit dependencies section
            if in_deps_section and line.startswith("[") and "dependencies" not in line:
                in_deps_section = False

            # Parse dependency lines
            if in_deps_section:
                matches = re.findall(dep_pattern, line)
                for package_name in matches:
                    normalized = package_name.replace("_", "-").lower()
                    if package_name in known_deps or normalized in known_deps:
                        found.add(package_name)

        return found

    def _parse_package_json(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse package.json dependencies and devDependencies.

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Match lines like: "openai": "^1.0.0" or "@anthropic/sdk": "latest"
        dep_pattern = r'["\']([a-zA-Z0-9@/_-]+)["\']\s*:\s*["\']'

        for match in re.finditer(dep_pattern, content):
            package_name = match.group(1)

            # Remove scope prefix if present (e.g., @anthropic/sdk -> sdk)
            base_name = package_name.split("/")[-1]

            # Check both full name and base name
            if package_name in known_deps or base_name in known_deps:
                found.add(package_name)

        return found

    def _scan_source_files(
        self,
        path: Path,
        declared_deps: set[str],
        seen_components: set[tuple[str, str]],
    ) -> list[AIComponent]:
        """Scan source files for AI SDK usage.

        Args:
            path: Root path to scan
            declared_deps: Set of declared dependencies from Phase A
            seen_components: Set of (sdk_name, file_path) tuples to avoid duplicates

        Returns:
            List of detected AI components
        """
        components: list[AIComponent] = []

        # Find all source code files
        source_files = self.iter_files(
            path, extensions=SCANNABLE_EXTENSIONS["code"]
        )

        for source_file in source_files:
            try:
                content = source_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                # Skip unreadable files
                continue

            lines = content.splitlines()

            # Track seen SDKs in this file for deduplication
            file_seen_sdks: set[str] = set()

            # Scan file line by line
            for line_num, line in enumerate(lines, start=1):
                # Check for API keys
                api_key_results = detect_api_key(line)
                for masked_key, provider, pattern in api_key_results:
                    component = AIComponent(
                        name=f"{provider} API Key",
                        type=ComponentType.llm_provider,
                        provider=provider,
                        usage_type=UsageType.unknown,
                        location=SourceLocation(
                            file_path=str(source_file),
                            line_number=line_num,
                            context_snippet=line.strip()[:200],
                        ),
                        flags=["hardcoded_api_key"],
                        source="code",
                    )
                    components.append(component)

                # Check each LLM pattern
                for pattern in LLM_PATTERNS:
                    # Check import patterns
                    import_matched = any(
                        re.search(import_pattern, line)
                        for import_pattern in pattern.import_patterns
                    )

                    # Check usage patterns
                    usage_matched = any(
                        re.search(usage_pattern, line)
                        for usage_pattern in pattern.usage_patterns
                    )

                    if import_matched or usage_matched:
                        # Only create one component per SDK per file
                        # (track the first occurrence)
                        if pattern.sdk_name in file_seen_sdks:
                            # But still scan for models on subsequent lines
                            if pattern.model_extraction and usage_matched:
                                model_match = re.search(pattern.model_extraction, line)
                                if model_match:
                                    model_name = model_match.group(1)
                                    flags: list[str] = []

                                    # Check for deprecated model
                                    if model_name in DEPRECATED_MODELS:
                                        flags.append("deprecated_model")

                                    # Check for unpinned model
                                    if not self._is_model_pinned(model_name):
                                        flags.append("unpinned_model")

                                    # Create a model component
                                    if flags:  # Only if there are issues
                                        component = AIComponent(
                                            name=f"{pattern.sdk_name} Model",
                                            type=ComponentType.model,
                                            provider=pattern.provider,
                                            model_name=model_name,
                                            usage_type=pattern.usage_type,
                                            location=SourceLocation(
                                                file_path=str(source_file),
                                                line_number=line_num,
                                                context_snippet=line.strip()[:200],
                                            ),
                                            flags=flags,
                                            source="code",
                                        )
                                        components.append(component)
                            continue

                        file_seen_sdks.add(pattern.sdk_name)

                        # Check for shadow AI
                        is_shadow_ai = not self._is_declared(
                            pattern.dep_names, declared_deps
                        )

                        # Extract model name if pattern supports it
                        model_name = ""
                        flags: list[str] = []

                        if pattern.model_extraction and usage_matched:
                            model_match = re.search(pattern.model_extraction, line)
                            if model_match:
                                model_name = model_match.group(1)

                                # Check for deprecated model
                                if model_name in DEPRECATED_MODELS:
                                    flags.append("deprecated_model")

                                # Check for unpinned model (just a bare name)
                                if not self._is_model_pinned(model_name):
                                    flags.append("unpinned_model")

                        if is_shadow_ai:
                            flags.append("shadow_ai")

                        component = AIComponent(
                            name=pattern.sdk_name,
                            type=pattern.component_type,
                            provider=pattern.provider,
                            model_name=model_name,
                            usage_type=pattern.usage_type,
                            location=SourceLocation(
                                file_path=str(source_file),
                                line_number=line_num,
                                context_snippet=line.strip()[:200],
                            ),
                            flags=flags,
                            source="code",
                        )
                        components.append(component)

        return components

    def _is_declared(self, dep_names: list[str], declared_deps: set[str]) -> bool:
        """Check if any of the dependency names are in declared_deps.

        Args:
            dep_names: List of possible package names for this SDK
            declared_deps: Set of declared dependencies

        Returns:
            True if at least one dep_name is in declared_deps
        """
        for dep_name in dep_names:
            # Check both exact match and normalized form
            if dep_name in declared_deps:
                return True

            # Normalize: replace - with _ and vice versa
            normalized_underscore = dep_name.replace("-", "_")
            normalized_dash = dep_name.replace("_", "-")

            if normalized_underscore in declared_deps or normalized_dash in declared_deps:
                return True

        return False

    def _is_model_pinned(self, model_name: str) -> bool:
        """Check if model name includes version pinning.

        Unpinned examples: "gpt-4", "claude-3-opus"
        Pinned examples: "gpt-4-0314", "claude-3-opus-20240229"

        Args:
            model_name: Model name to check

        Returns:
            True if model appears to have version pinning
        """
        # If model name contains a date pattern (e.g., 20240229, 0314) it's pinned
        if re.search(r"\d{4,8}", model_name):
            return True

        # If model name ends with a specific version number, it's pinned
        # e.g., gpt-3.5-turbo-0125
        if re.search(r"-\d{4}$", model_name):
            return True

        # Otherwise, consider it unpinned
        return False

    def _map_usage_type(self, usage_type_str: str) -> UsageType:
        """Map usage type string to UsageType enum.

        Args:
            usage_type_str: String representation of usage type

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
            "unknown": UsageType.unknown,
        }
        return mapping.get(usage_type_str, UsageType.unknown)

    def _determine_component_type(
        self, provider: str, usage_type_str: str
    ) -> ComponentType:
        """Determine component type based on provider and usage.

        Args:
            provider: Provider name
            usage_type_str: Usage type string

        Returns:
            ComponentType enum value
        """
        # Agent frameworks
        if usage_type_str in ("orchestration", "agent"):
            return ComponentType.agent_framework

        # Tool usage
        if usage_type_str == "tool_use":
            return ComponentType.tool

        # Default to LLM provider
        return ComponentType.llm_provider
