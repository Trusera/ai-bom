"""Cisco AIBOM JSON reporter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from ai_bom.models import ScanResult
from ai_bom.reporters.base import BaseReporter


class CiscoAIBOMReporter(BaseReporter):
    """Reporter that outputs Cisco AIBOM-compatible JSON."""

    def render(self, result: ScanResult) -> str:
        """Render scan result as Cisco AIBOM JSON."""
        relationships = getattr(result, "relationships", [])

        data = {
            "aibom_analysis": {
                "metadata": {
                    "run_id": str(uuid4()),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                "sources": {
                    "components": [
                        component.model_dump(mode="json") for component in result.components
                    ],
                    "relationships": relationships,
                },
                "summary": {
                    "total_components": result.summary.total_components,
                    "by_type": result.summary.by_type,
                    "by_severity": result.summary.by_severity,
                    "highest_risk_score": result.summary.highest_risk_score,
                },
            }
        }

        return json.dumps(data, indent=2)
