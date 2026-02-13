"""
Embedded Cedar-like policy evaluator for HTTP request filtering.

This module provides a lightweight Cedar policy engine adapted from the AI-BOM
Cedar gate for evaluating HTTP requests against security policies.

Supported policy patterns:
  - forbid ... when { request.url contains "api.deepseek.com" };
  - forbid ... when { request.hostname == "deepseek.com" };
  - forbid ... when { request.method == "POST" };
  - forbid ... when { request.path contains "/upload" };
  - permit ... when { request.hostname == "api.openai.com" };

Policy evaluation precedence:
  1. Explicit forbid rules are evaluated first
  2. Explicit permit rules are evaluated second
  3. If no rules match, default to ALLOW
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class PolicyAction(str, Enum):
    """Policy rule actions."""

    FORBID = "forbid"
    PERMIT = "permit"


class PolicyDecision(str, Enum):
    """Policy evaluation decision."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass
class PolicyRule:
    """A single parsed Cedar-like policy rule for HTTP requests."""

    action: PolicyAction
    field: str
    operator: str
    value: str
    raw: str


@dataclass
class EvaluationResult:
    """Result of evaluating a request against policies."""

    decision: PolicyDecision
    reason: str
    matched_rule: PolicyRule | None = None


# Regex patterns for Cedar-like policy syntax
# Matches: forbid ( principal, action == Action::"http", resource ) when { ... };
RULE_PATTERN = re.compile(
    r'(forbid|permit)\s*\(\s*principal\s*,\s*action\s*==\s*Action::"(\w+)"\s*,\s*resource\s*\)'
    r"\s*when\s*\{([^}]+)\}\s*;",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

# Matches conditions inside when { ... }
# e.g. request.url contains "api.deepseek.com"  or  request.method == "POST"
CONDITION_PATTERN = re.compile(
    r'request\.(\w+)\s*(==|!=|contains|startswith|endswith)\s*"([^"]+)"',
    re.MULTILINE | re.IGNORECASE,
)


def parse_policy(policy_text: str) -> list[PolicyRule]:
    """
    Parse a Cedar-like policy file into a list of rules.

    Args:
        policy_text: Cedar policy text content

    Returns:
        List of parsed PolicyRule objects
    """
    rules: list[PolicyRule] = []
    # Strip comments (// style)
    cleaned = re.sub(r"//[^\n]*", "", policy_text)

    for match in RULE_PATTERN.finditer(cleaned):
        action_str = match.group(1).lower()
        action = PolicyAction.FORBID if action_str == "forbid" else PolicyAction.PERMIT
        body = match.group(3).strip()

        for cond in CONDITION_PATTERN.finditer(body):
            field_name = cond.group(1).lower()
            operator = cond.group(2).lower()
            value = cond.group(3)

            rules.append(
                PolicyRule(
                    action=action,
                    field=field_name,
                    operator=operator,
                    value=value,
                    raw=match.group(0).strip(),
                )
            )

    return rules


def _match_condition(rule: PolicyRule, value: str) -> bool:
    """
    Check if a value matches a rule condition.

    Args:
        rule: The policy rule to evaluate
        value: The actual value to compare

    Returns:
        True if the condition matches (violates for forbid, allows for permit)
    """
    rule_value = rule.value.lower()
    value_lower = value.lower()

    if rule.operator == "==":
        return value_lower == rule_value
    elif rule.operator == "!=":
        return value_lower != rule_value
    elif rule.operator == "contains":
        return rule_value in value_lower
    elif rule.operator == "startswith":
        return value_lower.startswith(rule_value)
    elif rule.operator == "endswith":
        return value_lower.endswith(rule_value)

    return False


def evaluate_request(
    url: str,
    method: str,
    headers: dict[str, str] | None = None,
    rules: list[PolicyRule] | None = None,
) -> EvaluationResult:
    """
    Evaluate an HTTP request against Cedar policy rules.

    Evaluation logic:
    1. Check all FORBID rules - if any match, DENY
    2. Check all PERMIT rules - if any match, ALLOW
    3. If no rules match, default to ALLOW

    Args:
        url: The request URL
        method: HTTP method (GET, POST, etc.)
        headers: Optional request headers
        rules: List of policy rules to evaluate (empty = allow all)

    Returns:
        EvaluationResult with decision and reason
    """
    if not rules:
        return EvaluationResult(
            decision=PolicyDecision.ALLOW,
            reason="No policy rules configured",
        )

    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path or "/"

    # Build request context for evaluation
    request_data = {
        "url": url,
        "method": method.upper(),
        "hostname": hostname,
        "path": path,
        "scheme": parsed.scheme,
    }

    # Add headers to context if provided
    if headers:
        for key, value in headers.items():
            request_data[f"header_{key.lower().replace('-', '_')}"] = value

    # Phase 1: Check FORBID rules (highest priority)
    for rule in rules:
        if rule.action != PolicyAction.FORBID:
            continue

        field_value = request_data.get(rule.field, "")
        if field_value and _match_condition(rule, field_value):
            return EvaluationResult(
                decision=PolicyDecision.DENY,
                reason=(
                    f'Forbidden by policy: request.{rule.field} {rule.operator} "{rule.value}"'
                ),
                matched_rule=rule,
            )

    # Phase 2: Check PERMIT rules (second priority)
    for rule in rules:
        if rule.action != PolicyAction.PERMIT:
            continue

        field_value = request_data.get(rule.field, "")
        if field_value and _match_condition(rule, field_value):
            return EvaluationResult(
                decision=PolicyDecision.ALLOW,
                reason=(
                    f"Explicitly permitted by policy: request.{rule.field} "
                    f'{rule.operator} "{rule.value}"'
                ),
                matched_rule=rule,
            )

    # Default: Allow if no rules matched
    return EvaluationResult(
        decision=PolicyDecision.ALLOW,
        reason="No matching policy rules (default allow)",
    )


class CedarEvaluator:
    """
    Cedar policy evaluator for HTTP requests.

    This class loads and evaluates Cedar-like policies against HTTP requests,
    providing a decision (allow/deny) and reasoning.

    Example:
        >>> evaluator = CedarEvaluator.from_file("policy.cedar")
        >>> result = evaluator.evaluate("https://api.deepseek.com/v1/chat", "POST")
        >>> if result.decision == PolicyDecision.DENY:
        ...     print(f"Blocked: {result.reason}")
    """

    def __init__(self, rules: list[PolicyRule]) -> None:
        """
        Initialize the evaluator with parsed rules.

        Args:
            rules: List of PolicyRule objects
        """
        self.rules = rules

    @classmethod
    def from_file(cls, policy_path: str) -> CedarEvaluator:
        """
        Load a Cedar policy from a file.

        Args:
            policy_path: Path to the .cedar policy file

        Returns:
            CedarEvaluator instance

        Raises:
            FileNotFoundError: If policy file doesn't exist
        """
        with open(policy_path, encoding="utf-8") as f:
            policy_text = f.read()

        rules = parse_policy(policy_text)
        return cls(rules)

    @classmethod
    def from_text(cls, policy_text: str) -> CedarEvaluator:
        """
        Load a Cedar policy from text.

        Args:
            policy_text: Cedar policy text

        Returns:
            CedarEvaluator instance
        """
        rules = parse_policy(policy_text)
        return cls(rules)

    def evaluate(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> EvaluationResult:
        """
        Evaluate an HTTP request against loaded policies.

        Args:
            url: The request URL
            method: HTTP method (default: GET)
            headers: Optional request headers

        Returns:
            EvaluationResult with decision and reason
        """
        return evaluate_request(url, method, headers, self.rules)
