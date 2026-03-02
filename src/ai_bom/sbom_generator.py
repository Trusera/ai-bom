"""SBOM generator for AI-BOM."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_bom.models import ScanResult
from ai_bom.reporters import get_reporter


class SBOMGenerator:
    """Helper class to generate SBOMs in various formats."""

    def __init__(self, result: ScanResult) -> None:
        """Initialize the generator with a scan result.

        Args:
            result: The scan result to use for generation
        """
        self.result = result

    def generate_cyclonedx(self) -> str:
        """Generate a CycloneDX JSON SBOM.

        Returns:
            JSON string in CycloneDX format
        """
        reporter = get_reporter("cyclonedx")
        return reporter.render(self.result)

    def generate_spdx(self) -> str:
        """Generate an SPDX 3.0 JSON SBOM.

        Returns:
            JSON string in SPDX format
        """
        reporter = get_reporter("spdx3")
        return reporter.render(self.result)

    def write_to_file(self, format: str, path: str | Path) -> None:
        """Write the SBOM to a file.

        Args:
            format: Output format (e.g., 'cyclonedx', 'spdx3')
            path: Output file path
        """
        reporter = get_reporter(format)
        reporter.write(self.result, path)
