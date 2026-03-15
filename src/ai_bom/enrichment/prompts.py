"""Prompt templates for LLM-based model name extraction."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are an AI code analyst. Given a code snippet, extract the specific "
    "AI/ML model identifier being used (e.g. 'gpt-4o', 'claude-3-opus-20240229', "
    "'llama3'). Respond with ONLY a JSON object:\n"
    '{"model_name": "<model-id or empty string>", "provider": "<provider or empty string>"}\n'
    "If no specific model is identifiable, return empty strings. "
    "Do not include any other text, explanation, or markdown formatting."
)

USER_PROMPT_TEMPLATE = (
    "Extract the AI/ML model name from this code snippet.\n"
    "Component: {component_name} (provider: {provider})\n"
    "```\n{snippet}\n```"
)

BATCH_USER_PROMPT_TEMPLATE = (
    "Extract the AI/ML model name from each of the following code snippets. "
    "Return a JSON array with one object per snippet, in order:\n"
    '[{{"model_name": "...", "provider": "..."}}, ...]\n\n'
    "{entries}"
)

BATCH_ENTRY_TEMPLATE = (
    "--- Snippet {index} ---\n"
    "Component: {component_name} (provider: {provider})\n"
    "```\n{snippet}\n```\n"
)
