"""AI-BOM: AI Bill of Materials Discovery Scanner by Trusera."""

from ai_bom.sbom_generator import SBOMGenerator

__version__ = "3.4.2"


def get_version() -> str:
    """Return the current ai-bom version string."""
    return __version__
