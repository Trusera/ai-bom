"""Risk scoring utilities for AI components."""

from ai_bom.config import DEPRECATED_MODELS, RISK_WEIGHTS
from ai_bom.models import AIComponent, RiskAssessment, Severity

# Human-readable descriptions for each risk flag
FLAG_DESCRIPTIONS = {
    "hardcoded_api_key": "Hardcoded API key detected",
    "shadow_ai": "AI dependency not declared in project files",
    "internet_facing": "AI endpoint exposed to internet",
    "multi_agent_no_trust": "Multi-agent system without trust boundaries",
    "no_auth": "AI endpoint without authentication",
    "no_rate_limit": "No rate limiting on AI endpoint",
    "deprecated_model": "Using deprecated AI model",
    "no_error_handling": "No error handling for AI calls",
    "unpinned_model": "Model version not pinned",
    "webhook_no_auth": "n8n webhook without authentication",
    "code_http_tools": "Agent with code execution and HTTP tools",
    "mcp_unknown_server": "MCP client connected to unknown server",
    "agent_chain_no_validation": "Agent-to-agent chain without validation",
    "hardcoded_credentials": "Hardcoded credentials in workflow",
}


def score_component(component: AIComponent) -> RiskAssessment:
    """
    Score an AI component for risk.

    Evaluates component flags and model status against known risk weights
    to produce a comprehensive risk assessment with score, severity, and
    contributing factors.

    Args:
        component: The AI component to assess

    Returns:
        RiskAssessment with score (0-100), severity level, and list of
        contributing risk factors
    """
    score = 0
    factors: list[str] = []

    # Process component flags
    for flag in component.flags:
        if flag in RISK_WEIGHTS:
            weight = RISK_WEIGHTS[flag]
            score += weight

            # Get human-readable description
            description = FLAG_DESCRIPTIONS.get(flag, flag.replace("_", " ").title())
            factors.append(f"{description} (+{weight})")

    # Check for deprecated models
    if component.model_name and component.model_name in DEPRECATED_MODELS:
        weight = RISK_WEIGHTS.get("deprecated_model", 0)
        if weight > 0:
            score += weight
            description = FLAG_DESCRIPTIONS.get("deprecated_model", "Using deprecated AI model")
            factors.append(f"{description} (+{weight})")

    # Cap score at 100
    score = min(score, 100)

    # Determine severity level
    if score >= 76:
        severity = Severity.critical
    elif score >= 51:
        severity = Severity.high
    elif score >= 26:
        severity = Severity.medium
    else:
        severity = Severity.low

    return RiskAssessment(
        score=score,
        severity=severity,
        factors=factors
    )
