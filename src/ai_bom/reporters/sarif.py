"""SARIF 2.1.0 reporter for GitHub Code Scanning integration."""
from __future__ import annotations

import json
from pathlib import Path

from ai_bom import __version__
from ai_bom.models import AIComponent, ScanResult, Severity
from ai_bom.reporters.base import BaseReporter

# Map severity to SARIF level
_SEVERITY_TO_LEVEL = {
    Severity.critical: "error",
    Severity.high: "error",
    Severity.medium: "warning",
    Severity.low: "note",
}


def _make_rule_id(component: AIComponent) -> str:
    """Build a stable rule ID from component attributes."""
    # Normalise: lowercase, replace spaces/underscores with dashes
    name_slug = component.name.lower().replace(" ", "-").replace("_", "-")
    return f"ai-bom/{name_slug}"


def _build_rules(components: list[AIComponent]) -> list[dict]:
    """Deduplicate components into SARIF rule descriptors."""
    seen: dict[str, dict] = {}
    for comp in components:
        rule_id = _make_rule_id(comp)
        if rule_id in seen:
            continue
        rule: dict = {
            "id": rule_id,
            "shortDescription": {"text": comp.name},
            "defaultConfiguration": {
                "level": _SEVERITY_TO_LEVEL.get(comp.risk.severity, "note"),
            },
        }
        if comp.risk.factors:
            rule["helpUri"] = "https://github.com/trusera/ai-bom"
            rule["fullDescription"] = {"text": "; ".join(comp.risk.factors)}
        seen[rule_id] = rule
    return list(seen.values())


def _build_result(
    component: AIComponent, target_path: str, rule_index_map: dict[str, int]
) -> dict:
    """Convert a single AIComponent to a SARIF result object."""
    rule_id = _make_rule_id(component)

    message_parts = [component.name]
    if component.provider:
        message_parts.append(f"provider={component.provider}")
    if component.model_name:
        message_parts.append(f"model={component.model_name}")
    if component.flags:
        message_parts.append(f"flags={','.join(component.flags)}")
    message_text = " | ".join(message_parts)

    result: dict = {
        "ruleId": rule_id,
        "ruleIndex": rule_index_map.get(rule_id, 0),
        "level": _SEVERITY_TO_LEVEL.get(component.risk.severity, "note"),
        "message": {"text": message_text},
        "properties": {
            "risk_score": component.risk.score,
            "component_type": component.type.value,
            "usage_type": component.usage_type.value,
            "source_scanner": component.source,
        },
    }

    if component.flags:
        result["properties"]["flags"] = component.flags

    # Build location
    file_path = component.location.file_path
    if file_path and file_path != "dependency files":
        # Make path relative to target for SARIF
        try:
            rel = str(Path(file_path).relative_to(Path(target_path).resolve()))
        except ValueError:
            rel = file_path

        physical_location: dict = {
            "artifactLocation": {"uri": rel, "uriBaseId": "%SRCROOT%"},
        }
        if component.location.line_number:
            physical_location["region"] = {
                "startLine": component.location.line_number,
            }
        result["locations"] = [{"physicalLocation": physical_location}]

    return result


class SARIFReporter(BaseReporter):
    """Reporter that outputs SARIF 2.1.0 JSON for GitHub Code Scanning."""

    def render(self, result: ScanResult) -> str:
        """Render scan result as SARIF 2.1.0 JSON.

        Args:
            result: The scan result to render

        Returns:
            JSON string in SARIF 2.1.0 format
        """
        rules = _build_rules(result.components)
        rule_index_map = {rule["id"]: idx for idx, rule in enumerate(rules)}
        results = [
            _build_result(comp, result.target_path, rule_index_map)
            for comp in result.components
        ]

        sarif = {
            "$schema": (
                "https://raw.githubusercontent.com/oasis-tcs/"
                "sarif-spec/release-2.1/sarif-2.1/schema/"
                "sarif-schema-2.1.0.json"
            ),
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "ai-bom",
                            "organization": "Trusera",
                            "version": __version__,
                            "informationUri": "https://github.com/trusera/ai-bom",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

        return json.dumps(sarif, indent=2)
