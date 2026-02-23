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
from ai_bom.detectors.model_registry import lookup_model
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
        return file_ext in SCANNABLE_EXTENSIONS["code"] or path.name in SCANNABLE_EXTENSIONS["deps"]

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
            provider, usage_type_str = KNOWN_AI_PACKAGES.get(dep_name, ("Unknown", "unknown"))

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
            source_components = self._scan_single_source_file(path, declared_deps, seen_components)
        else:
            source_components = self._scan_source_files(scan_dir, declared_deps, seen_components)
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
        # Get files matching exact names from the list
        dep_files_list = list(self.iter_files(path, filenames=SCANNABLE_EXTENSIONS["deps"]))

        # Also find .csproj files (pattern matching) since they can have any name
        for file_path in path.rglob("*.csproj"):
            if file_path.is_file() and file_path not in dep_files_list:
                dep_files_list.append(file_path)

        dep_files = dep_files_list

        for dep_file in dep_files:
            filename = dep_file.name.lower()

            try:
                content = dep_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                # Skip unreadable files
                continue

            # Parse based on file type
            if filename == "requirements.txt" or filename == "pipfile":
                declared_deps.update(self._parse_requirements_format(content, all_known_ai_deps))
            elif filename == "pyproject.toml":
                declared_deps.update(self._parse_pyproject_toml(content, all_known_ai_deps))
            elif filename == "package.json":
                declared_deps.update(self._parse_package_json(content, all_known_ai_deps))
            elif filename == "cargo.toml":
                declared_deps.update(self._parse_cargo_toml(content, all_known_ai_deps))
            elif filename == "go.mod":
                declared_deps.update(self._parse_go_mod(content, all_known_ai_deps))
            elif filename == "gemfile":
                declared_deps.update(self._parse_gemfile(content, all_known_ai_deps))
            elif filename == "pom.xml":
                declared_deps.update(self._parse_pom_xml(content, all_known_ai_deps))
            elif filename in ("build.gradle", "build.gradle.kts"):
                declared_deps.update(self._parse_gradle(content, all_known_ai_deps))
            elif filename.endswith(".csproj"):
                declared_deps.update(self._parse_csproj(content, all_known_ai_deps))

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
        elif filename == "cargo.toml":
            return self._parse_cargo_toml(content, all_known_ai_deps)
        elif filename == "go.mod":
            return self._parse_go_mod(content, all_known_ai_deps)
        elif filename == "gemfile":
            return self._parse_gemfile(content, all_known_ai_deps)
        elif filename == "pom.xml":
            return self._parse_pom_xml(content, all_known_ai_deps)
        elif filename in ("build.gradle", "build.gradle.kts"):
            return self._parse_gradle(content, all_known_ai_deps)
        elif filename.endswith(".csproj"):
            return self._parse_csproj(content, all_known_ai_deps)
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
            for _, provider, _ in api_key_results:
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
                import_matched = any(re.search(ip, line) for ip in pat.import_patterns)
                usage_matched = any(re.search(up, line) for up in pat.usage_patterns)
                if import_matched or usage_matched:
                    if pat.sdk_name in file_seen_sdks:
                        if pat.model_extraction and usage_matched:
                            model_match = re.search(pat.model_extraction, line)
                            if model_match:
                                model_name = model_match.group(1)
                                model_flags: list[str] = []
                                if model_name in DEPRECATED_MODELS:
                                    model_flags.append("deprecated_model")
                                if not self._is_model_pinned(model_name):
                                    model_flags.append("unpinned_model")
                                if model_flags:
                                    provider = pat.provider
                                    metadata = lookup_model(model_name)
                                    if metadata:
                                        provider = str(metadata["provider"])
                                    component = AIComponent(
                                        name=f"{pat.sdk_name} Model",
                                        type=ComponentType.model,
                                        provider=provider,
                                        model_name=model_name,
                                        usage_type=pat.usage_type,
                                        location=SourceLocation(
                                            file_path=str(path),
                                            line_number=line_num,
                                            context_snippet=line.strip()[:200],
                                        ),
                                        flags=model_flags,
                                        source="code",
                                    )
                                    components.append(component)
                        continue
                    file_seen_sdks.add(pat.sdk_name)
                    is_shadow_ai = not self._is_declared(pat.dep_names, declared_deps)
                    model_name = ""
                    flags: list[str] = []
                    provider = pat.provider

                    if pat.model_extraction and usage_matched:
                        model_match = re.search(pat.model_extraction, line)
                        if model_match:
                            model_name = model_match.group(1)
                            if model_name in DEPRECATED_MODELS:
                                flags.append("deprecated_model")
                            if not self._is_model_pinned(model_name):
                                flags.append("unpinned_model")
                            metadata = lookup_model(model_name)
                            if metadata:
                                provider = str(metadata["provider"])

                    if is_shadow_ai:
                        flags.append("shadow_ai")
                    component = AIComponent(
                        name=pat.sdk_name,
                        type=pat.component_type,
                        provider=provider,
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

    def _parse_requirements_format(self, content: str, known_deps: set[str]) -> set[str]:
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
        source_files = self.iter_files(path, extensions=SCANNABLE_EXTENSIONS["code"])

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
                for _, provider, _ in api_key_results:
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
                for llm_pat in LLM_PATTERNS:
                    # Check import patterns
                    import_matched = any(
                        re.search(import_pattern, line)
                        for import_pattern in llm_pat.import_patterns
                    )

                    # Check usage patterns
                    usage_matched = any(
                        re.search(usage_pattern, line) for usage_pattern in llm_pat.usage_patterns
                    )

                    if import_matched or usage_matched:
                        # Only create one component per SDK per file
                        # (track the first occurrence)
                        if llm_pat.sdk_name in file_seen_sdks:
                            # But still scan for models on subsequent lines
                            if llm_pat.model_extraction and usage_matched:
                                model_match = re.search(llm_pat.model_extraction, line)
                                if model_match:
                                    model_name = model_match.group(1)
                                    model_flags: list[str] = []

                                    # Check for deprecated model
                                    if model_name in DEPRECATED_MODELS:
                                        model_flags.append("deprecated_model")

                                    # Check for unpinned model
                                    if not self._is_model_pinned(model_name):
                                        model_flags.append("unpinned_model")

                                    # Create a model component
                                    if model_flags:
                                        provider = llm_pat.provider
                                        metadata = lookup_model(model_name)
                                        if metadata:
                                            provider = str(metadata["provider"])
                                        component = AIComponent(
                                            name=f"{llm_pat.sdk_name} Model",
                                            type=ComponentType.model,
                                            provider=provider,
                                            model_name=model_name,
                                            usage_type=llm_pat.usage_type,
                                            location=SourceLocation(
                                                file_path=str(source_file),
                                                line_number=line_num,
                                                context_snippet=line.strip()[:200],
                                            ),
                                            flags=model_flags,
                                            source="code",
                                        )
                                        components.append(component)
                            continue

                        file_seen_sdks.add(llm_pat.sdk_name)

                        # Check for shadow AI
                        is_shadow_ai = not self._is_declared(llm_pat.dep_names, declared_deps)

                        # Extract model name if pattern supports it
                        model_name = ""
                        sdk_flags: list[str] = []

                        provider = llm_pat.provider
                        if llm_pat.model_extraction and usage_matched:
                            model_match = re.search(llm_pat.model_extraction, line)
                            if model_match:
                                model_name = model_match.group(1)

                                # Check for deprecated model
                                if model_name in DEPRECATED_MODELS:
                                    sdk_flags.append("deprecated_model")

                                # Check for unpinned model (just a bare name)
                                if not self._is_model_pinned(model_name):
                                    sdk_flags.append("unpinned_model")

                                metadata = lookup_model(model_name)
                                if metadata:
                                    provider = str(metadata["provider"])

                        if is_shadow_ai:
                            sdk_flags.append("shadow_ai")

                        component = AIComponent(
                            name=llm_pat.sdk_name,
                            type=llm_pat.component_type,
                            provider=provider,
                            model_name=model_name,
                            usage_type=llm_pat.usage_type,
                            location=SourceLocation(
                                file_path=str(source_file),
                                line_number=line_num,
                                context_snippet=line.strip()[:200],
                            ),
                            flags=sdk_flags,
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
        # If model name ends with a specific version number, it's pinned
        # e.g., gpt-3.5-turbo-0125
        return bool(re.search(r"\d{4,8}", model_name) or re.search(r"-\d{4}$", model_name))

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

    def _determine_component_type(self, provider: str, usage_type_str: str) -> ComponentType:
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

    def _parse_cargo_toml(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse Cargo.toml dependencies section (Rust).

        Looks for dependencies like:
        async-openai = "0.14"
        anthropic-sdk = { version = "0.1" }

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()
        in_deps_section = False

        for line in content.splitlines():
            line = line.strip()

            # Detect [dependencies] section
            if line.startswith("[dependencies"):
                in_deps_section = True
                continue

            # Exit dependencies section when we hit another section
            if in_deps_section and line.startswith("[") and "dependencies" not in line:
                in_deps_section = False

            # Parse dependency lines
            if in_deps_section and "=" in line:
                # Extract package name (before =)
                package_name = line.split("=")[0].strip()

                # Normalize: replace - with _ and vice versa
                normalized_underscore = package_name.replace("-", "_")
                normalized_dash = package_name.replace("_", "-")

                if (
                    package_name in known_deps
                    or normalized_underscore in known_deps
                    or normalized_dash in known_deps
                ):
                    found.add(package_name)

        return found

    def _parse_go_mod(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse go.mod require section (Go).

        Looks for require statements like:
        require github.com/sashabaranov/go-openai v1.5.0

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        for line in content.splitlines():
            line = line.strip()

            # Match require lines
            if line.startswith("require ") or (not line.startswith("//") and "/" in line):
                # Extract package path
                parts = line.split()
                if len(parts) >= 2:
                    package_path = parts[0] if parts[0] != "require" else parts[1]

                    # Check if full path matches known deps
                    if package_path in known_deps:
                        found.add(package_path)

        return found

    def _parse_gemfile(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse Gemfile gem declarations (Ruby).

        Looks for gem statements like:
        gem 'ruby-openai'
        gem "anthropic", "~> 0.1"

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Match gem declarations
        gem_pattern = r"gem\s+['\"]([a-zA-Z0-9_-]+)['\"]"

        for match in re.finditer(gem_pattern, content):
            gem_name = match.group(1)

            # Normalize
            normalized_underscore = gem_name.replace("-", "_")
            normalized_dash = gem_name.replace("_", "-")

            if (
                gem_name in known_deps
                or normalized_underscore in known_deps
                or normalized_dash in known_deps
            ):
                found.add(gem_name)

        return found

    def _parse_pom_xml(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse pom.xml Maven dependencies (Java).

        Looks for dependency elements like:
        <dependency>
            <groupId>com.langchain4j</groupId>
            <artifactId>langchain4j</artifactId>
        </dependency>

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Extract groupId and artifactId pairs
        group_id_pattern = r"<groupId>([^<]+)</groupId>"
        artifact_id_pattern = r"<artifactId>([^<]+)</artifactId>"

        lines = content.splitlines()
        current_group_id = None

        for line in lines:
            line = line.strip()

            # Match groupId
            group_match = re.search(group_id_pattern, line)
            if group_match:
                current_group_id = group_match.group(1)

            # Match artifactId
            artifact_match = re.search(artifact_id_pattern, line)
            if artifact_match and current_group_id:
                artifact_id = artifact_match.group(1)

                # Build full coordinate
                full_name = f"{current_group_id}:{artifact_id}"

                # Check if matches known deps
                if full_name in known_deps or artifact_id in known_deps:
                    found.add(full_name)

                current_group_id = None  # Reset after matching

        return found

    def _parse_gradle(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse build.gradle or build.gradle.kts Gradle dependencies (Java/Kotlin).

        Looks for implementation/compile statements like:
        implementation 'com.langchain4j:langchain4j:0.27.0'
        implementation("spring-ai:0.8.0")

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Match implementation/compile lines for both Groovy and Kotlin DSL
        # Groovy: implementation 'group:artifact:version'
        # Kotlin: implementation("group:artifact:version")
        dep_pattern = (
            r"(?:implementation|compile|api|testImplementation)"
            r"\s*(?:\()?['\"]([a-zA-Z0-9._:/-]+)"
        )

        for match in re.finditer(dep_pattern, content):
            dep_string = match.group(1)

            # Extract group:artifact from dep string
            if ":" in dep_string:
                # Full coordinate format (group:artifact:version or artifact:version)
                parts = dep_string.split(":")

                if len(parts) >= 2:
                    # Check if it's full coordinate (group:artifact) or just (artifact:version)
                    # If parts[0] is a known dep, it's artifact:version format
                    if parts[0] in known_deps:
                        # artifact:version format (e.g., spring-ai:0.8.0)
                        found.add(parts[0])
                    else:
                        # group:artifact:version format (e.g., com.langchain4j:langchain4j:0.27.0)
                        group_artifact = f"{parts[0]}:{parts[1]}"
                        if group_artifact in known_deps or parts[1] in known_deps:
                            found.add(group_artifact)
            else:
                # Just artifact name
                if dep_string in known_deps:
                    found.add(dep_string)

        return found

    def _parse_csproj(self, content: str, known_deps: set[str]) -> set[str]:
        """Parse .csproj PackageReference elements (.NET).

        Looks for PackageReference elements like:
        <PackageReference Include="Azure.AI.OpenAI" Version="1.0.0" />
        <PackageReference Include="Microsoft.SemanticKernel" Version="1.0.0" />

        Args:
            content: File content
            known_deps: Set of known AI package names

        Returns:
            Set of found AI package names
        """
        found: set[str] = set()

        # Match PackageReference Include attribute
        package_pattern = r'<PackageReference\s+Include="([^"]+)"'

        for match in re.finditer(package_pattern, content):
            package_name = match.group(1)

            if package_name in known_deps:
                found.add(package_name)

        return found
