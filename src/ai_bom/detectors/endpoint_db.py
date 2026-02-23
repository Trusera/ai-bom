"""
Endpoint Database and API Key Detection.

Utilities for matching URLs against known AI service endpoints and detecting
API keys in source code or configuration files.
"""

from __future__ import annotations

import re

from ai_bom.config import API_KEY_PATTERNS, KNOWN_AI_ENDPOINTS


def match_endpoint(url: str) -> tuple[str, str] | None:
    """
    Match a URL against known AI service endpoints.

    Searches through the configured endpoint patterns and returns provider
    and usage type for the first matching pattern.

    Args:
        url: URL string to check (e.g., "https://api.openai.com/v1/chat/completions")

    Returns:
        Tuple of (provider, usage_type) if matched, None otherwise

    Examples:
        >>> match_endpoint("https://api.openai.com/v1/chat/completions")
        ("OpenAI", "completion")

        >>> match_endpoint("https://api.anthropic.com/v1/messages")
        ("Anthropic", "completion")

        >>> match_endpoint("https://example.com/api")
        None
    """
    for pattern, provider, usage_type in KNOWN_AI_ENDPOINTS:
        if pattern.search(url, re.IGNORECASE):
            return (provider, usage_type)
    return None


def detect_api_key(text: str) -> list[tuple[str, str, str]]:
    """
    Detect API keys in text using configured patterns.

    Scans text for API key patterns and returns all matches. Keys are masked
    for security (first 8 chars + "..." + last 4 chars). Placeholder keys
    (containing "demo", "test", "example", "xxx", "your") are still reported
    as they indicate AI usage intention.

    Args:
        text: Text content to scan (source code, config file, etc.)

    Returns:
        List of tuples: (masked_key, provider, pattern_matched)

    Examples:
        >>> text = 'OPENAI_API_KEY="sk-proj-abc123xyz789"'
        >>> detect_api_key(text)
        [("sk-proj-...xyz789", "OpenAI", "sk-[a-zA-Z0-9]{32,}")]

        >>> text = 'ANTHROPIC_API_KEY="sk-ant-test123"'
        >>> detect_api_key(text)
        [("sk-ant-t...st123", "Anthropic", "sk-ant-[a-zA-Z0-9_-]{32,}")]
    """
    results: list[tuple[str, str, str]] = []

    for pattern, provider in API_KEY_PATTERNS:
        for match in pattern.finditer(text):
            # Use the first capture group if present, otherwise the full match
            key = match.group(1) if match.lastindex else match.group(0)

            # Mask the key for security
            if len(key) <= 12:
                masked_key = key[:4] + "..." + key[-2:]
            else:
                masked_key = key[:8] + "..." + key[-4:]

            # Include all keys - even placeholders indicate AI usage
            results.append((masked_key, provider, str(pattern.pattern)))

    return results
