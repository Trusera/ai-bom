"""Docker scanner for AI-BOM: Detects AI containers in Dockerfiles and compose files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Pattern

import yaml

from ai_bom.config import AI_DOCKER_IMAGES
from ai_bom.models import AIComponent, ComponentType, SourceLocation, UsageType
from ai_bom.scanners.base import BaseScanner


class DockerScanner(BaseScanner):
    """Scanner for Docker and Docker Compose files to detect AI containers.

    Detects AI usage in:
    - Dockerfiles (FROM statements with AI images)
    - Docker Compose files (services with AI images or GPU configuration)

    Also identifies GPU usage, model mounts, and AI-related environment variables.
    """

    name = "docker"
    description = "Scan Dockerfiles & compose for AI containers"

    # Patterns for AI-related environment variables
    AI_ENV_PATTERNS = [
        "OPENAI",
        "ANTHROPIC",
        "HUGGING",
        "HF_TOKEN",
        "COHERE",
        "MISTRAL",
        "OLLAMA",
        "BEDROCK",
        "AZURE_OPENAI",
        "GOOGLE_AI",
        "VERTEX",
        "REPLICATE",
        "TOGETHER",
        "MODEL_NAME",
        "MODEL_ID",
        "LLM_",
        "AI_API",
        "EMBEDDING",
    ]

    def __init__(self) -> None:
        """Initialize the Docker scanner."""
        super().__init__()
        # Compile AI image patterns for efficient matching
        self._image_patterns: list[Pattern[str]] = [
            re.compile(re.escape(prefix)) for prefix in AI_DOCKER_IMAGES
        ]

    def supports(self, path: Path) -> bool:
        """Check if this scanner should run on the given path.

        Args:
            path: Directory or file path to check

        Returns:
            True if path contains Docker-related files, False otherwise
        """
        if path.is_file():
            filename = path.name.lower()
            # Match Dockerfile* or *compose*.yml/yaml
            if filename.startswith("dockerfile") or filename.endswith(".dockerfile"):
                return True
            if "compose" in filename and (
                filename.endswith(".yml") or filename.endswith(".yaml")
            ):
                return True
            return False

        # For directories, check if any Docker files exist
        if path.is_dir():
            try:
                # Quick check for common Docker files
                for file_path in path.rglob("*"):
                    if not file_path.is_file():
                        continue
                    filename = file_path.name.lower()
                    if filename.startswith("dockerfile") or filename.endswith(".dockerfile"):
                        return True
                    if "compose" in filename and (
                        filename.endswith(".yml") or filename.endswith(".yaml")
                    ):
                        return True
            except (OSError, PermissionError):
                pass

        return False

    def scan(self, path: Path) -> list[AIComponent]:
        """Scan Docker files for AI containers and configurations.

        Args:
            path: Directory or file path to scan

        Returns:
            List of detected AI components with metadata
        """
        components: list[AIComponent] = []

        if path.is_file():
            # Scan single file
            filename = path.name.lower()
            if filename.startswith("dockerfile") or filename.endswith(".dockerfile"):
                components.extend(self._scan_dockerfile(path))
            elif "compose" in filename and (
                filename.endswith(".yml") or filename.endswith(".yaml")
            ):
                components.extend(self._scan_compose(path))
        else:
            # Scan directory
            # Find all Dockerfiles
            for dockerfile in self.iter_files(
                path,
                filenames={
                    "Dockerfile",
                    "dockerfile",
                },
            ):
                components.extend(self._scan_dockerfile(dockerfile))

            # Find files with "dockerfile" in name or .dockerfile extension
            for dockerfile in path.rglob("*"):
                if not dockerfile.is_file():
                    continue
                filename = dockerfile.name.lower()
                if (
                    "dockerfile" in filename
                    and filename != "dockerfile"
                    and filename != "dockerfile"
                ):
                    components.extend(self._scan_dockerfile(dockerfile))

            # Find all compose files
            for compose_file in path.rglob("*compose*.y*ml"):
                if compose_file.is_file():
                    components.extend(self._scan_compose(compose_file))

        return components

    def _scan_dockerfile(self, file_path: Path) -> list[AIComponent]:
        """Parse a Dockerfile and extract AI image references.

        Args:
            file_path: Path to the Dockerfile

        Returns:
            List of AI components found in the Dockerfile
        """
        components: list[AIComponent] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            for line_num, line in enumerate(lines, start=1):
                # Strip comments and whitespace
                line = line.strip()
                if "#" in line:
                    line = line.split("#")[0].strip()

                # Look for FROM instructions
                if not line.upper().startswith("FROM"):
                    continue

                # Extract image reference
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue

                image_ref = parts[1].strip()

                # Remove platform specification if present
                if image_ref.startswith("--platform="):
                    parts = image_ref.split(maxsplit=1)
                    if len(parts) < 2:
                        continue
                    image_ref = parts[1].strip()

                # Check if image matches any AI pattern
                for pattern in self._image_patterns:
                    if pattern.search(image_ref):
                        # Parse image name and version
                        image_name, version = self._parse_image_ref(image_ref)

                        component = AIComponent(
                            name=image_name,
                            type=ComponentType.container,
                            version=version,
                            provider=self._extract_provider(image_name),
                            location=SourceLocation(
                                file_path=str(file_path.resolve()),
                                line_number=line_num,
                                context_snippet=line,
                            ),
                            usage_type=UsageType.unknown,
                            source="docker",
                            metadata={"image": image_ref, "file_type": "dockerfile"},
                        )
                        components.append(component)
                        break

        except (OSError, UnicodeDecodeError):
            # Log error but continue scanning
            pass

        return components

    def _scan_compose(self, file_path: Path) -> list[AIComponent]:
        """Parse a Docker Compose file and extract AI services.

        Args:
            file_path: Path to the compose file

        Returns:
            List of AI components found in the compose file
        """
        components: list[AIComponent] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                return components

            services = data.get("services", {})
            if not isinstance(services, dict):
                return components

            for service_name, service_config in services.items():
                if not isinstance(service_config, dict):
                    continue

                # Check image field
                image = service_config.get("image", "")
                if isinstance(image, str) and image:
                    for pattern in self._image_patterns:
                        if pattern.search(image):
                            # Parse image name and version
                            image_name, version = self._parse_image_ref(image)

                            # Check for GPU
                            has_gpu = self._check_gpu(service_config)

                            # Check for model mounts
                            has_models = self._check_model_mounts(service_config)

                            # Check for AI environment variables
                            has_ai_env = self._check_ai_env_vars(service_config)

                            metadata: dict[str, bool | str | list[str]] = {
                                "image": image,
                                "service_name": service_name,
                                "file_type": "compose",
                            }

                            if has_gpu:
                                metadata["gpu"] = True

                            if has_models:
                                metadata["has_model_mounts"] = True

                            if has_ai_env:
                                metadata["has_ai_env_vars"] = True

                            component = AIComponent(
                                name=f"{service_name} ({image_name})",
                                type=ComponentType.container,
                                version=version,
                                provider=self._extract_provider(image_name),
                                location=SourceLocation(
                                    file_path=str(file_path.resolve()),
                                    line_number=None,
                                    context_snippet=f"Service: {service_name}",
                                ),
                                usage_type=UsageType.unknown,
                                source="docker",
                                metadata=metadata,
                            )
                            components.append(component)
                            break

                # Check build.context for AI-related Dockerfiles
                build = service_config.get("build")
                if build:
                    build_context = None
                    dockerfile = None

                    if isinstance(build, str):
                        build_context = build
                    elif isinstance(build, dict):
                        build_context = build.get("context", "")
                        dockerfile = build.get("dockerfile", "Dockerfile")

                    # If we have a build context, check the referenced Dockerfile
                    if build_context:
                        # Construct path to the Dockerfile
                        compose_dir = file_path.parent
                        context_path = compose_dir / build_context
                        dockerfile_path = context_path / (dockerfile or "Dockerfile")

                        if dockerfile_path.exists():
                            # Scan the Dockerfile
                            dockerfile_components = self._scan_dockerfile(dockerfile_path)
                            # Update service name in components
                            for comp in dockerfile_components:
                                comp.name = f"{service_name} ({comp.name})"
                                comp.metadata["service_name"] = service_name
                                comp.metadata["file_type"] = "compose_build"

                                # Check for GPU, model mounts, and env vars
                                has_gpu = self._check_gpu(service_config)
                                has_models = self._check_model_mounts(service_config)
                                has_ai_env = self._check_ai_env_vars(service_config)

                                if has_gpu:
                                    comp.metadata["gpu"] = True
                                if has_models:
                                    comp.metadata["has_model_mounts"] = True
                                if has_ai_env:
                                    comp.metadata["has_ai_env_vars"] = True

                            components.extend(dockerfile_components)

        except yaml.YAMLError:
            # YAML parse error, skip this file
            pass
        except (OSError, UnicodeDecodeError):
            # File read error, skip
            pass

        return components

    def _parse_image_ref(self, image_ref: str) -> tuple[str, str]:
        """Parse Docker image reference into name and version.

        Args:
            image_ref: Docker image reference (e.g., "ollama/ollama:latest")

        Returns:
            Tuple of (image_name, version)
        """
        # Remove "as builder" or similar aliases
        if " as " in image_ref.lower():
            image_ref = image_ref.split(" as ")[0].strip()

        # Split by colon to separate name and tag
        if ":" in image_ref:
            parts = image_ref.rsplit(":", 1)
            image_name = parts[0]
            version = parts[1]
        else:
            image_name = image_ref
            version = "latest"

        # Extract digest if present
        if "@sha256:" in image_name:
            image_name = image_name.split("@")[0]

        return image_name, version

    def _extract_provider(self, image_name: str) -> str:
        """Extract provider name from image name.

        Args:
            image_name: Docker image name

        Returns:
            Provider name or empty string
        """
        # Map common image prefixes to providers
        provider_map = {
            "ollama": "Ollama",
            "vllm": "vLLM",
            "huggingface": "HuggingFace",
            "nvidia": "NVIDIA",
            "llama.cpp": "llama.cpp",
            "chromadb": "ChromaDB",
            "qdrant": "Qdrant",
            "weaviate": "Weaviate",
        }

        image_lower = image_name.lower()
        for key, provider in provider_map.items():
            if key in image_lower:
                return provider

        return ""

    def _check_gpu(self, service_config: dict) -> bool:
        """Check if service has GPU configuration.

        Args:
            service_config: Service configuration dictionary

        Returns:
            True if GPU is configured, False otherwise
        """
        # Check deploy.resources.reservations.devices
        deploy = service_config.get("deploy", {})
        if not isinstance(deploy, dict):
            return False

        resources = deploy.get("resources", {})
        if not isinstance(resources, dict):
            return False

        reservations = resources.get("reservations", {})
        if not isinstance(reservations, dict):
            return False

        devices = reservations.get("devices", [])
        if not isinstance(devices, list):
            return False

        # Check for NVIDIA driver or GPU capabilities
        for device in devices:
            if not isinstance(device, dict):
                continue

            driver = device.get("driver", "")
            capabilities = device.get("capabilities", [])

            if driver == "nvidia":
                return True

            if isinstance(capabilities, list):
                for cap in capabilities:
                    if isinstance(cap, str) and "gpu" in cap.lower():
                        return True
                    elif isinstance(cap, list):
                        for subcap in cap:
                            if isinstance(subcap, str) and "gpu" in subcap.lower():
                                return True

        return False

    def _check_model_mounts(self, service_config: dict) -> bool:
        """Check if service has model-related volume mounts.

        Args:
            service_config: Service configuration dictionary

        Returns:
            True if model mounts are found, False otherwise
        """
        volumes = service_config.get("volumes", [])
        if not isinstance(volumes, list):
            return False

        # Patterns indicating model storage
        model_patterns = ["/models", "/weights", ".gguf", "/lora"]

        for volume in volumes:
            if isinstance(volume, str):
                volume_lower = volume.lower()
                for pattern in model_patterns:
                    if pattern in volume_lower:
                        return True
            elif isinstance(volume, dict):
                target = volume.get("target", "")
                source = volume.get("source", "")
                combined = f"{source} {target}".lower()
                for pattern in model_patterns:
                    if pattern in combined:
                        return True

        return False

    def _check_ai_env_vars(self, service_config: dict) -> bool:
        """Check if service has AI-related environment variables.

        Args:
            service_config: Service configuration dictionary

        Returns:
            True if AI env vars are found, False otherwise
        """
        environment = service_config.get("environment", [])

        # Handle environment as list
        if isinstance(environment, list):
            for env_var in environment:
                if not isinstance(env_var, str):
                    continue
                # Format: "KEY=value" or just "KEY"
                key = env_var.split("=")[0].upper()
                for pattern in self.AI_ENV_PATTERNS:
                    if pattern in key:
                        return True

        # Handle environment as dict
        elif isinstance(environment, dict):
            for key in environment.keys():
                key_upper = str(key).upper()
                for pattern in self.AI_ENV_PATTERNS:
                    if pattern in key_upper:
                        return True

        return False
