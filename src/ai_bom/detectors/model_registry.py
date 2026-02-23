"""
Model Registry.

Central registry mapping AI model names to provider metadata and deprecation status.
Supports exact matches and prefix-based lookups for model identification.
"""

from __future__ import annotations

# Comprehensive model registry mapping model name patterns to metadata
MODEL_REGISTRY: dict[str, dict[str, str | bool]] = {
    # OpenAI Models
    "gpt-4o": {"provider": "OpenAI", "deprecated": False},
    "gpt-4o-mini": {"provider": "OpenAI", "deprecated": False},
    "gpt-4-turbo": {"provider": "OpenAI", "deprecated": False},
    "gpt-4": {"provider": "OpenAI", "deprecated": False},
    "gpt-3.5-turbo": {"provider": "OpenAI", "deprecated": True},
    "o1": {"provider": "OpenAI", "deprecated": False},
    "o1-mini": {"provider": "OpenAI", "deprecated": False},
    "o1-preview": {"provider": "OpenAI", "deprecated": False},
    # OpenAI Multimodal
    "dall-e-3": {"provider": "OpenAI", "deprecated": False},
    "dall-e-2": {"provider": "OpenAI", "deprecated": False},
    "whisper-1": {"provider": "OpenAI", "deprecated": False},
    "tts-1": {"provider": "OpenAI", "deprecated": False},
    "tts-1-hd": {"provider": "OpenAI", "deprecated": False},
    # OpenAI Embeddings
    "text-embedding-3-large": {"provider": "OpenAI", "deprecated": False},
    "text-embedding-3-small": {"provider": "OpenAI", "deprecated": False},
    "text-embedding-ada-002": {"provider": "OpenAI", "deprecated": True},
    # Anthropic Models
    "claude-3-5-sonnet": {"provider": "Anthropic", "deprecated": False},
    "claude-3-5-haiku": {"provider": "Anthropic", "deprecated": False},
    "claude-3-opus": {"provider": "Anthropic", "deprecated": False},
    "claude-3-sonnet": {"provider": "Anthropic", "deprecated": False},
    "claude-3-haiku": {"provider": "Anthropic", "deprecated": False},
    "claude-2": {"provider": "Anthropic", "deprecated": True},
    "claude-instant": {"provider": "Anthropic", "deprecated": True},
    # Google Models
    "gemini-1.5-pro": {"provider": "Google", "deprecated": False},
    "gemini-1.5-flash": {"provider": "Google", "deprecated": False},
    "gemini-pro": {"provider": "Google", "deprecated": False},
    "gemini-ultra": {"provider": "Google", "deprecated": False},
    # Cohere Models
    "command-r-plus": {"provider": "Cohere", "deprecated": False},
    "command-r": {"provider": "Cohere", "deprecated": False},
    "command": {"provider": "Cohere", "deprecated": False},
    # Mistral Models
    "mistral-large": {"provider": "Mistral", "deprecated": False},
    "mistral-medium": {"provider": "Mistral", "deprecated": False},
    "mistral-small": {"provider": "Mistral", "deprecated": False},
    "mixtral-8x7b": {"provider": "Mistral", "deprecated": False},
    # Meta Models
    "llama-3": {"provider": "Meta", "deprecated": False},
    "llama-2": {"provider": "Meta", "deprecated": False},
    "codellama": {"provider": "Meta", "deprecated": False},
    # xAI Models
    "grok-2": {"provider": "xAI", "deprecated": False},
    "grok-1.5": {"provider": "xAI", "deprecated": False},
    "grok-1": {"provider": "xAI", "deprecated": False},
    "grok-beta": {"provider": "xAI", "deprecated": False},
    "grok": {"provider": "xAI", "deprecated": False},
    # Alibaba Models
    "qwen-max": {"provider": "Alibaba", "deprecated": False},
    "qwen-plus": {"provider": "Alibaba", "deprecated": False},
    "qwen-turbo": {"provider": "Alibaba", "deprecated": False},
    "qwen-coder": {"provider": "Alibaba", "deprecated": False},
    "qwen2.5": {"provider": "Alibaba", "deprecated": False},
    "qwen2": {"provider": "Alibaba", "deprecated": False},
    "qwen1.5": {"provider": "Alibaba", "deprecated": False},
    "qwen": {"provider": "Alibaba", "deprecated": False},
}


def lookup_model(model_name: str) -> dict[str, str | bool] | None:
    """
    Look up a model name in the registry.

    Tries exact match first, then falls back to prefix matching.
    For prefix matches, the longest matching prefix wins.

    Args:
        model_name: Model identifier to look up (e.g., "gpt-4o-2024-05-13")

    Returns:
        Metadata dict with "provider" and "deprecated" keys, or None if not found

    Examples:
        >>> lookup_model("gpt-4o")
        {"provider": "OpenAI", "deprecated": False}

        >>> lookup_model("gpt-4o-2024-05-13")
        {"provider": "OpenAI", "deprecated": False}

        >>> lookup_model("claude-3-opus-20240229")
        {"provider": "Anthropic", "deprecated": False}

        >>> lookup_model("unknown-model")
        None
    """
    # Try exact match first
    if model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name]

    # Fall back to prefix matching - longest prefix wins
    best_match: tuple[str, dict[str, str | bool]] | None = None
    best_length = 0

    for registered_name, metadata in MODEL_REGISTRY.items():
        if model_name.startswith(registered_name) and len(registered_name) > best_length:
            best_match = (registered_name, metadata)
            best_length = len(registered_name)

    if best_match:
        return best_match[1]

    return None
