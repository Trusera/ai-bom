#!/usr/bin/env python3
"""
Cedar-like policy gate for AI-BOM scan results.

Evaluates AI-BOM scan output against a simplified Cedar policy file.
Used in CI pipelines (GitHub Actions, GitLab CI) to enforce security
policies on discovered AI/LLM components.

Supported policy patterns:
  - forbid (principal, action, resource) when { ... };
  - forbid (principal, action == Action::"deploy", resource) when { ... };
  - forbid ... when { resource.severity == "critical" };
  - forbid ... when { resource.provider == "DeepSeek" };
  - forbid ... when { resource.component_type == "llm-api" };
  - forbid ... when { resource.risk_score > 75 };

Usage:
  python3 cedar-gate.py <scan-results.json> <policy.cedar> [options]

Options:
  --summary <path>          Write violation report to file (GitHub Actions summary)
  --fail-on-severity <sev>  Only fail on violations at or above this severity
  --annotations             Emit GitHub Actions annotations (::error, ::warning)
  --entities <path>         Path to Cedar entities JSON file for additional context

Exit codes:
  0 = all policies passed
  1 = one or more policy violations
  2 = input/parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PolicyRule:
    """A single parsed Cedar-like forbid rule."""

    action: str
    field: str
    operator: str
    value: str | int | float
    raw: str


@dataclass
class Violation:
    """A policy violation found during evaluation."""

    rule: PolicyRule
    component_name: str
    component_type: str
    actual_value: Any
    severity: str = ""
    file_path: str = ""
    line_number: int = 0


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "none": 0}

# Regex patterns for Cedar-like policy syntax
# Pattern 1: forbid (principal, action == Action::"deploy", resource) when { ... };
RULE_PATTERN_TYPED = re.compile(
    r'forbid\s*\(\s*principal\s*,\s*action\s*==\s*Action::"(\w+)"\s*,\s*resource\s*\)'
    r"\s*when\s*\{([^}]+)\}\s*;",
    re.MULTILINE | re.DOTALL,
)

# Pattern 2: forbid (principal, action, resource) when { ... };
RULE_PATTERN_SIMPLE = re.compile(
    r"forbid\s*\(\s*principal\s*,\s*action\s*,\s*resource\s*\)"
    r"\s*when\s*\{([^}]+)\}\s*;",
    re.MULTILINE | re.DOTALL,
)

# Matches conditions inside when { ... }
# e.g. resource.severity == "critical"  or  resource.risk_score > 75
CONDITION_PATTERN = re.compile(
    r'resource\.(\w+)\s*(==|!=|>|>=|<|<=)\s*"?([^";]+?)"?\s*$',
    re.MULTILINE,
)


def parse_policy(policy_text: str) -> list[PolicyRule]:
    """Parse a Cedar-like policy file into a list of rules."""
    rules: list[PolicyRule] = []
    # Strip comments (// style)
    cleaned = re.sub(r"//[^\n]*", "", policy_text)

    # Match typed action rules: action == Action::"deploy"
    for match in RULE_PATTERN_TYPED.finditer(cleaned):
        action = match.group(1)
        body = match.group(2).strip()

        for cond in CONDITION_PATTERN.finditer(body):
            field_name = cond.group(1)
            operator = cond.group(2)
            raw_value = cond.group(3).strip()

            value = _parse_value(raw_value)
            rules.append(
                PolicyRule(
                    action=action,
                    field=field_name,
                    operator=operator,
                    value=value,
                    raw=match.group(0).strip(),
                )
            )

    # Match simple rules: (principal, action, resource)
    for match in RULE_PATTERN_SIMPLE.finditer(cleaned):
        body = match.group(1).strip()

        for cond in CONDITION_PATTERN.finditer(body):
            field_name = cond.group(1)
            operator = cond.group(2)
            raw_value = cond.group(3).strip()

            value = _parse_value(raw_value)
            rules.append(
                PolicyRule(
                    action="*",
                    field=field_name,
                    operator=operator,
                    value=value,
                    raw=match.group(0).strip(),
                )
            )

    return rules


def _parse_value(raw_value: str) -> str | int | float:
    """Try to parse a value as number, fall back to string."""
    try:
        return int(raw_value)
    except ValueError:
        try:
            return float(raw_value)
        except ValueError:
            return raw_value


def evaluate_condition(rule: PolicyRule, component: dict[str, Any]) -> bool:
    """Check if a single component violates a rule. Returns True if violated."""
    # Map Cedar field names to AI-BOM scan result keys
    field_map = {
        "severity": "severity",
        "provider": "provider",
        "component_type": "component_type",
        "type": "component_type",
        "risk_score": "risk_score",
        "name": "name",
    }

    key = field_map.get(rule.field, rule.field)
    actual = component.get(key)
    if actual is None:
        return False

    # Severity comparison uses ordinal ranking
    if rule.field == "severity":
        actual_rank = SEVERITY_ORDER.get(str(actual).lower(), 0)
        target_rank = SEVERITY_ORDER.get(str(rule.value).lower(), 0)

        if rule.operator == "==":
            return actual_rank == target_rank
        if rule.operator == "!=":
            return actual_rank != target_rank
        if rule.operator == ">=":
            return actual_rank >= target_rank
        if rule.operator == ">":
            return actual_rank > target_rank
        if rule.operator == "<=":
            return actual_rank <= target_rank
        if rule.operator == "<":
            return actual_rank < target_rank

    # Numeric comparison
    if isinstance(rule.value, (int, float)):
        try:
            actual_num = float(actual)
        except (TypeError, ValueError):
            return False

        if rule.operator == "==":
            return actual_num == rule.value
        if rule.operator == "!=":
            return actual_num != rule.value
        if rule.operator == ">":
            return actual_num > rule.value
        if rule.operator == ">=":
            return actual_num >= rule.value
        if rule.operator == "<":
            return actual_num < rule.value
        if rule.operator == "<=":
            return actual_num <= rule.value

    # String comparison (case-insensitive)
    actual_str = str(actual).lower()
    target_str = str(rule.value).lower()

    if rule.operator == "==":
        return actual_str == target_str
    if rule.operator == "!=":
        return actual_str != target_str

    return False


def evaluate(
    components: list[dict[str, Any]],
    rules: list[PolicyRule],
    entities: dict[str, Any] | None = None,
) -> list[Violation]:
    """Evaluate all components against all rules. Returns list of violations."""
    violations: list[Violation] = []

    # Merge entity attributes into components if entities file provided
    entity_map: dict[str, dict[str, Any]] = {}
    if entities:
        for entity in entities.get("entities", []):
            uid = entity.get("uid", {})
            entity_id = uid.get("id", "") if isinstance(uid, dict) else str(uid)
            if entity_id:
                entity_map[entity_id] = entity.get("attrs", {})

    for component in components:
        # Enrich component with entity attributes if available
        enriched = dict(component)
        comp_name = component.get("name", "")
        if comp_name in entity_map:
            for k, v in entity_map[comp_name].items():
                if k not in enriched:
                    enriched[k] = v

        for rule in rules:
            if evaluate_condition(rule, enriched):
                violations.append(
                    Violation(
                        rule=rule,
                        component_name=enriched.get("name", "unknown"),
                        component_type=enriched.get("component_type", "unknown"),
                        actual_value=enriched.get(rule.field, "N/A"),
                        severity=str(enriched.get("severity", "")).lower(),
                        file_path=enriched.get("file_path", ""),
                        line_number=enriched.get("line_number", 0),
                    )
                )

    return violations


def filter_by_severity(violations: list[Violation], min_severity: str) -> list[Violation]:
    """Filter violations to only include those at or above the given severity."""
    threshold = SEVERITY_ORDER.get(min_severity.lower(), 0)
    if threshold == 0:
        return violations

    filtered = []
    for v in violations:
        # Determine the severity of the violation
        sev = v.severity or "none"
        if SEVERITY_ORDER.get(sev, 0) >= threshold:
            filtered.append(v)
    return filtered


def extract_components(scan_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the component list from various AI-BOM output formats."""
    # Direct list at top level
    if isinstance(scan_data, list):
        return scan_data

    # Standard AI-BOM JSON output: { "components": [...] }
    if "components" in scan_data:
        return scan_data["components"]

    # CycloneDX format: { "components": [...] } nested differently
    if "bomFormat" in scan_data and "components" in scan_data:
        return scan_data["components"]

    # SARIF format: extract from results
    if "runs" in scan_data:
        components = []
        for run in scan_data.get("runs", []):
            for result in run.get("results", []):
                comp: dict[str, Any] = {
                    "name": result.get("ruleId", "unknown"),
                    "severity": result.get("level", "none"),
                    "component_type": result.get("properties", {}).get("component_type", "unknown"),
                    "provider": result.get("properties", {}).get("provider", "unknown"),
                    "risk_score": result.get("properties", {}).get("risk_score", 0),
                }
                # Extract file location from SARIF
                locations = result.get("locations", [])
                if locations:
                    phys = locations[0].get("physicalLocation", {})
                    artifact = phys.get("artifactLocation", {})
                    comp["file_path"] = artifact.get("uri", "")
                    region = phys.get("region", {})
                    comp["line_number"] = region.get("startLine", 0)
                components.append(comp)
        return components

    # Fallback: treat the whole dict as a single component
    if "name" in scan_data:
        return [scan_data]

    return []


def format_violation_report(violations: list[Violation]) -> str:
    """Format violations into a human-readable report."""
    lines = [
        "## Cedar Policy Gate - FAILED",
        "",
        f"**{len(violations)} violation(s) found**",
        "",
        "| # | Component | Type | Rule | Actual Value |",
        "|---|-----------|------|------|--------------|",
    ]

    for i, v in enumerate(violations, 1):
        condition = f"`resource.{v.rule.field} {v.rule.operator} {v.rule.value}`"
        lines.append(
            f"| {i} | {v.component_name} | {v.component_type} | {condition} | {v.actual_value} |"
        )

    lines.extend(
        [
            "",
            "### Policy rules that triggered",
            "",
        ]
    )

    seen_rules: set[str] = set()
    for v in violations:
        if v.rule.raw not in seen_rules:
            seen_rules.add(v.rule.raw)
            lines.append(f"```cedar\n{v.rule.raw}\n```")
            lines.append("")

    return "\n".join(lines)


def emit_annotations(violations: list[Violation]) -> None:
    """Emit GitHub Actions annotations for each violation."""
    for v in violations:
        level = "error" if v.severity in ("critical", "high") else "warning"
        msg = (
            f"Policy violation: {v.component_name} ({v.component_type}) — "
            f"resource.{v.rule.field} {v.rule.operator} {v.rule.value} "
            f"(actual: {v.actual_value})"
        )
        if v.file_path and v.line_number:
            print(f"::{level} file={v.file_path},line={v.line_number}::{msg}")
        elif v.file_path:
            print(f"::{level} file={v.file_path}::{msg}")
        else:
            print(f"::{level} ::{msg}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cedar-like policy gate for AI-BOM scan results")
    parser.add_argument("results", help="Path to scan results JSON file")
    parser.add_argument("policy", help="Path to Cedar policy file")
    parser.add_argument("--summary", help="Path to write violation report")
    parser.add_argument(
        "--fail-on-severity",
        choices=["critical", "high", "medium", "low"],
        help="Only fail on violations at or above this severity",
    )
    parser.add_argument(
        "--annotations",
        action="store_true",
        help="Emit GitHub Actions ::error/::warning annotations",
    )
    parser.add_argument(
        "--entities",
        help="Path to Cedar entities JSON file for additional context",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    results_path = Path(args.results)
    policy_path = Path(args.policy)

    # Load scan results
    if not results_path.exists():
        print(f"Error: scan results file not found: {results_path}", file=sys.stderr)
        return 2

    try:
        scan_data = json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {results_path}: {e}", file=sys.stderr)
        return 2

    # Load policy
    if not policy_path.exists():
        print(f"Error: policy file not found: {policy_path}", file=sys.stderr)
        return 2

    policy_text = policy_path.read_text(encoding="utf-8")

    # Load entities (optional)
    entities: dict[str, Any] | None = None
    if args.entities:
        entities_path = Path(args.entities)
        if entities_path.exists():
            try:
                entities = json.loads(entities_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"Warning: invalid JSON in entities file: {e}", file=sys.stderr)

    # Parse
    rules = parse_policy(policy_text)
    if not rules:
        print("Warning: no rules found in policy file", file=sys.stderr)
        print("Cedar policy gate: PASSED (no rules to evaluate)")
        return 0

    components = extract_components(scan_data)
    if not components:
        print("Cedar policy gate: PASSED (no components found in scan results)")
        return 0

    print(f"Evaluating {len(rules)} rule(s) against {len(components)} component(s)...")

    # Evaluate
    violations = evaluate(components, rules, entities)

    # Filter by severity threshold if specified
    if args.fail_on_severity and violations:
        violations = filter_by_severity(violations, args.fail_on_severity)

    if violations:
        report = format_violation_report(violations)
        print(report)

        # Emit GitHub Actions annotations
        if args.annotations:
            emit_annotations(violations)

        # Write GitHub Actions summary if path provided
        if args.summary:
            summary_path = Path(args.summary)
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(report)
                f.write("\n")

        return 1

    print(f"Cedar policy gate: PASSED ({len(rules)} rules, {len(components)} components)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
